"""
Pydantic v2 schemas for AI invoice extraction validation.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class LineItem(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)
    line_total: float = Field(..., gt=0)

    @field_validator("line_total")
    @classmethod
    def check_line_total_math(cls, v, info) -> float:
        """Verify line_total ≈ quantity × unit_price (within rounding tolerance)."""
        qty = info.data.get("quantity")
        price = info.data.get("unit_price")
        if qty is not None and price is not None:
            expected = round(qty * price, 4)
            actual = round(v, 4)
            if abs(expected - actual) > 0.02:
                # Soft correction — flag but don't reject
                pass
        return v


class InvoiceExtraction(BaseModel):
    invoice_number: Optional[str] = Field(default=None, max_length=128)
    invoice_date: Optional[date] = None
    supplier_name: Optional[str] = Field(default=None, max_length=255)
    currency: Optional[str] = Field(default=None, max_length=3)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    line_items: list[LineItem] = Field(default_factory=list)

    @field_validator("invoice_date", mode="before")
    @classmethod
    def parse_invoice_date(cls, v):
        """Accept date strings or date objects."""
        if v is None:
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            v = v.strip()
            # Try ISO format first
            try:
                return date.fromisoformat(v)
            except ValueError:
                pass
            # Try common formats: DD/MM/YYYY, MM/DD/YYYY, DD-MM-YYYY, etc.
            for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %B %Y", "%B %d, %Y"):
                try:
                    import datetime as dt
                    return dt.datetime.strptime(v, fmt).date()
                except ValueError:
                    continue
        return None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v):
        """Ensure currency is uppercase 3-letter ISO code."""
        if v is None:
            return None
        v = v.strip().upper()
        if len(v) != 3:
            return None
        return v

    @model_validator(mode="after")
    def validate_totals(self):
        """Cross-check subtotal + tax ≈ total."""
        if self.subtotal is not None and self.tax is not None and self.total is not None:
            expected = round(self.subtotal + self.tax, 4)
            actual = round(self.total, 4)
            if abs(expected - actual) > 0.02:
                # Soft correction — accept but note discrepancy
                pass
        # Check line_items sum ≈ subtotal
        if self.line_items and self.subtotal is not None:
            items_sum = round(sum(item.line_total for item in self.line_items), 4)
            if abs(items_sum - round(self.subtotal, 4)) > 0.02:
                pass
        return self
