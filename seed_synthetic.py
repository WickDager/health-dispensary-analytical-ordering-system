"""
Seed the HDAOS dev database with realistic synthetic data for the
usage simulation (seed_and_simulate phase).

Usage:
    cd health-dispensary-analytical-ordering-system
    python seed_synthetic.py            # create-if-missing, update otherwise
    python seed_synthetic.py --wipe     # delete previously seeded rows first

Everything is namespaced with the prefix "SYN-" so it can be identified
and re-created idempotently.  Invoice text files are written to
scratch_invoices/ for the AI-ingest workflow.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hdaos.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.accounts.models import Role  # noqa: E402
from apps.approvals.models import ApprovalRequest  # noqa: E402
from apps.audit.models import AIIngestAudit, AuditLog  # noqa: E402
from apps.catalog.models import Product, Supplier  # noqa: E402
from apps.crm.models import (  # noqa: E402
    Account,
    Activity,
    Campaign,
    Contact,
    Lead,
    Opportunity,
    PipelineStage,
    RefillReminder,
    Tag,
    Task,
)
from apps.lots.models import Lot  # noqa: E402
from apps.orders.models import Order, OrderItem  # noqa: E402

PREFIX = "SYN-"
User = get_user_model()

INVOICES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch_invoices")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def info(msg: str) -> None:
    print(f"  {msg}")


def get_or_none(model, **kwargs):
    return model.objects.filter(**kwargs).first()


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
def seed_users():
    print("[users]")
    users = {
        "devadmin": ("devadmin", Role.ADMIN, True),
        "synsales": ("synsales", Role.SALES, False),
        "synpharm": ("synpharm", Role.PHARMACIST, True),
        "synproc": ("synproc", Role.PROCUREMENT, False),
    }
    out = {}
    for key, (username, role, mrn) in users.items():
        u = get_or_none(User, username=username)
        if u is None:
            u = User.objects.create_user(
                username=username,
                password="e2e-pass-1234",
                email=f"{username}@synthetic.local",
                role=role,
                mrn_access=mrn,
                is_active=True,
            )
            info(f"created {username} ({role})")
        else:
            # Deterministic credentials: reset password + sync role/active flags.
            u.set_password("e2e-pass-1234")
            u.is_active = True
            u.role = role
            u.mrn_access = mrn
            u.save(update_fields=["password", "is_active", "role", "mrn_access"])
        out[key] = u
    return out


# ---------------------------------------------------------------------------
# catalog
# ---------------------------------------------------------------------------
def seed_catalog():
    print("[catalog]")
    suppliers = [
        ("SYN-MediCorp Global", "orders@medicorp.example", 5, 500.0, 4.6),
        ("SYN-PharmaDirect Ltd", "sales@pharmadirect.example", 3, 200.0, 4.2),
        ("SYN-HealthSource Co", "hello@healthsource.example", 7, 1000.0, 3.9),
    ]
    sup_objs = {}
    for name, email, lead, min_order, rating in suppliers:
        s = get_or_none(Supplier, name=name)
        if s is None:
            s = Supplier.objects.create(
                name=name, contact_email=email, lead_time=lead,
                min_order_value=min_order, rating=rating,
            )
            info(f"supplier {name}")
        sup_objs[name] = s

    today = date.today()
    products = [
        # name, api, strength, soh, min, max, unit_cost, pack, reorder, supplier
        ("SYN-Amoxicillin 500mg", "Amoxicillin", "500mg", 850, 150, 1200, 0.45, 100, 250, "SYN-MediCorp Global"),   # HEALTHY
        ("SYN-Ibuprofen 400mg", "Ibuprofen", "400mg", 180, 100, 900, 0.12, 100, 200, "SYN-PharmaDirect Ltd"),        # LOW
        ("SYN-Metformin 850mg", "Metformin", "850mg", 60, 120, 800, 0.20, 50, 150, "SYN-MediCorp Global"),           # CRITICAL
        ("SYN-Atorvastatin 20mg", "Atorvastatin", "20mg", 0, 80, 600, 0.33, 30, 100, "SYN-HealthSource Co"),         # STOCKOUT
        ("SYN-Lisinopril 10mg", "Lisinopril", "10mg", 220, 60, 500, 0.18, 50, 150, "SYN-PharmaDirect Ltd"),          # HEALTHY
        ("SYN-Omeprazole 20mg", "Omeprazole", "20mg", 95, 40, 400, 0.27, 50, 120, "SYN-MediCorp Global"),            # LOW
        ("SYN-Salbutamol Inhaler", "Salbutamol", "100mcg", 45, 25, 150, 4.50, 10, 60, "SYN-HealthSource Co"),        # HEALTHY
        ("SYN-Cetirizine 10mg", "Cetirizine", "10mg", 30, 50, 300, 0.09, 100, 80, "SYN-PharmaDirect Ltd"),           # CRITICAL
    ]
    prod_objs = {}
    for (name, api, strength, soh, mn, mx, cost, pack, reorder, sup) in products:
        p = get_or_none(Product, name=name)
        if p is None:
            p = Product.objects.create(
                name=name, api=api, strength=strength, soh=soh,
                min_stock=mn, max_stock=mx, unit_cost=cost, pack_size=pack,
                reorder_point=reorder, supplier=sup_objs[sup],
            )
            info(f"product {name} (soh={soh})")
        prod_objs[name] = p

    # ---- lots -------------------------------------------------------------
    # Layout per product: enough stock to support the FEFO dispense demo,
    # plus boundary expiries that trigger the tiered alerts.
    lot_specs = [
        # product, batch, expiry_days, qty, locked
        ("SYN-Amoxicillin 500mg", "SYN-BATCH-A1", -10, 50, False),    # expired -> auto-lock target
        ("SYN-Amoxicillin 500mg", "SYN-BATCH-A2", 30, 120, False),    # CRITICAL tier (exactly 30d)
        ("SYN-Amoxicillin 500mg", "SYN-BATCH-A3", 400, 680, False),   # main usable stock
        ("SYN-Ibuprofen 400mg", "SYN-BATCH-I1", 60, 180, False),      # WARN tier (exactly 60d)
        ("SYN-Metformin 850mg", "SYN-BATCH-M1", 90, 60, False),       # INFO tier (exactly 90d)
        ("SYN-Lisinopril 10mg", "SYN-BATCH-L1", 25, 100, False),      # CRITICAL tier
        ("SYN-Lisinopril 10mg", "SYN-BATCH-L2", 200, 120, False),     # main usable stock
        ("SYN-Omeprazole 20mg", "SYN-BATCH-O1", 45, 95, False),
        ("SYN-Salbutamol Inhaler", "SYN-BATCH-S1", 15, 45, False),    # CRITICAL tier
        ("SYN-Cetirizine 10mg", "SYN-BATCH-C1", 75, 30, False),
        ("SYN-Cetirizine 10mg", "SYN-BATCH-C2", 500, 120, True),      # pre-locked (LOT_UNLOCK demo)
    ]
    for (pname, batch, days, qty, locked) in lot_specs:
        lot = get_or_none(Lot, batch_number=batch)
        if lot is None:
            exp = today + timedelta(days=days)
            Lot.objects.create(
                product=prod_objs[pname],
                batch_number=batch,
                manufacture_date=exp - timedelta(days=540),
                expiry_date=exp,
                quantity=qty,
                is_locked=locked,
            )
    info(f"lots ensured ({Lot.objects.filter(batch_number__startswith=PREFIX).count()} SYN lots)")
    return prod_objs, sup_objs


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------
def seed_crm(users):
    print("[crm]")
    admin = users["devadmin"]
    sales = users["synsales"]

    tag_diabetes, _ = Tag.objects.get_or_create(name="SYN-diabetes")
    tag_tier1, _ = Tag.objects.get_or_create(name="SYN-tier-1-hospital")

    st_marys = get_or_none(Account, name="SYN-St Mary's Hospital")
    if st_marys is None:
        st_marys = Account.objects.create(
            name="SYN-St Mary's Hospital", account_type="HOSPITAL",
            billing_address="120 Healthcare Dr, Springfield", owner=sales,
        )
        st_marys.tags.add(tag_tier1)
        info("account SYN-St Mary's Hospital")

    lakeside = get_or_none(Account, name="SYN-Lakeside Clinic")
    if lakeside is None:
        lakeside = Account.objects.create(
            name="SYN-Lakeside Clinic", account_type="CLINIC", owner=sales,
        )
        lakeside.tags.add(tag_diabetes)
        info("account SYN-Lakeside Clinic")

    today = date.today()

    def ensure_contact(first, last, ctype, account, email, mrn, consent, tags=()):
        c = get_or_none(Contact, first_name=first, last_name=last, contact_type=ctype)
        if c is None:
            c = Contact.objects.create(
                contact_type=ctype, first_name=first, last_name=last,
                email=email, mrn=mrn, account=account, owner=sales,
                consent_marketing=consent,
            )
            for t in tags:
                c.tags.add(t)
        return c

    alice = ensure_contact("Alice", "Nguyen", "PATIENT", lakeside,
                           "alice.nguyen@example.com", "SYN-MRN-1001", True, (tag_diabetes,))
    bob = ensure_contact("Bob", "Okafor", "PATIENT", lakeside,
                         "bob.okafor@example.com", "SYN-MRN-1002", False)
    carla = ensure_contact("Carla", "Reyes", "PATIENT", st_marys,
                           "carla.reyes@example.com", "SYN-MRN-1003", True)
    dmitri = ensure_contact("Dmitri", "Ivanov", "PRESCRIBER", st_marys,
                            "d.i.ivanov@example.com", None, False)
    elena = ensure_contact("Elena", "Marsh", "BUYER", st_marys,
                           "elena.marsh@example.com", None, True, (tag_tier1,))
    info("contacts ensured (5)")

    lead = get_or_none(Lead, name="SYN-Riverside Care Group")
    if lead is None:
        lead = Lead.objects.create(
            name="SYN-Riverside Care Group", source="Trade show",
            status="QUALIFIED", est_value=25000.0, owner=sales,
        )
        info("lead SYN-Riverside Care Group (QUALIFIED)")

    opp = get_or_none(Opportunity, name="SYN-St Mary's — Annual Supply Contract")
    if opp is None:
        opp = Opportunity.objects.create(
            name="SYN-St Mary's — Annual Supply Contract", account=st_marys,
            stage=PipelineStage.NEGOTIATION, amount=48000.0, probability=65,
            expected_close_date=today + timedelta(days=45), owner=sales,
        )
        info("opportunity NEGOTIATION $48k")

    act = get_or_none(Activity, subject="SYN-Quarterly review call", account=st_marys)
    if act is None:
        Activity.objects.create(
            activity_type="CALL", subject="SYN-Quarterly review call",
            body="Discussed renewing the annual supply contract; Elena wants volume pricing.",
            contact=elena, account=st_marys, opportunity=opp, created_by=sales,
        )
        info("activity logged")

    task = get_or_none(Task, title="SYN-Send Elena volume pricing sheet")
    if task is None:
        Task.objects.create(
            title="SYN-Send Elena volume pricing sheet", due_date=today,
            status="OPEN", assignee=sales, contact=elena, opportunity=opp,
        )
        info("task due today (TASK_DUE scan target)")

    camp = get_or_none(Campaign, name="SYN-Spring Diabetes Refill Drive")
    if camp is None:
        Campaign.objects.create(
            name="SYN-Spring Diabetes Refill Drive", campaign_type="REFILL",
            scheduled_for=timezone.now() + timedelta(days=14),
        )
        info("campaign SYN-Spring Diabetes Refill Drive")

    prods = {p.name: p for p in Product.objects.filter(name__startswith=PREFIX)}
    ref1 = get_or_none(RefillReminder, contact=alice, product=prods["SYN-Metformin 850mg"])
    if ref1 is None:
        RefillReminder.objects.create(
            contact=alice, product=prods["SYN-Metformin 850mg"],
            interval_days=30, next_due_date=today, active=True,
        )
        info("refill reminder due today (REFILL_DUE scan target)")
    ref2 = get_or_none(RefillReminder, contact=bob, product=prods["SYN-Salbutamol Inhaler"])
    if ref2 is None:
        RefillReminder.objects.create(
            contact=bob, product=prods["SYN-Salbutamol Inhaler"],
            interval_days=90, next_due_date=today + timedelta(days=45), active=True,
        )

    return {
        "accounts": [st_marys, lakeside],
        "contacts": [alice, bob, carla, dmitri, elena],
        "lead": lead, "opportunity": opp,
        "tags": [tag_diabetes, tag_tier1],
    }


# ---------------------------------------------------------------------------
# orders (one existing PENDING order so the ledger is not empty)
# ---------------------------------------------------------------------------
def seed_orders(prod_objs, sup_objs):
    print("[orders]")
    if get_or_none(Order, status="PENDING") is None:
        order = Order.objects.create(
            supplier=sup_objs["SYN-PharmaDirect Ltd"], status="PENDING",
            total_cost=0.0,
        )
        OrderItem.objects.create(
            order=order, product=prod_objs["SYN-Cetirizine 10mg"],
            quantity=250, unit_cost=0.09,
        )
        order.total_cost = 22.50
        order.save(update_fields=["total_cost"])
        info("seeded one PENDING order")


# ---------------------------------------------------------------------------
# synthetic AI-ingest audit (a *successful* extraction, as if an LLM had run)
# ---------------------------------------------------------------------------
INVOICE_1_TEXT = """MEDICORP GLOBAL - PHARMACEUTICAL SUPPLIER
Invoice Number: SYN-INV-2026-0114
Invoice Date: 2026-09-20
Bill To: SYN Health Dispensary

Description                Qty    Unit Price    Line Total
SYN-Amoxicillin 500mg      500    0.42          210.00
SYN-Ibuprofen 400mg        400    0.11           44.00
SYN-Metformin 850mg        300    0.19           57.00

Subtotal:                                        311.00
Tax (0%):                                          0.00
Total:                                           311.00
"""

INVOICE_2_TEXT = """PHARMADIRECT LTD - DELIVERY NOTE / INVOICE
Invoice Number: SYN-INV-2026-0115
Invoice Date: 2026-09-24

Item                              Quantity   Price
SYN-Omeprazole 20mg               200        0.25
SYN-Lisinopril 10mg               150        0.17
SYN-Cetirizine 10mg               350        0.08

Subtotal: 128.50
Tax: 0.00
Total: 128.50
Currency: USD
"""

INVOICE_3_TEXT = "###MALFORMED### not a real invoice, no structure at all 12345 !!!"


def seed_synthetic_audit(users):
    """Create one successful AIIngestAudit whose validated_output matches
    INVOICE_1_TEXT.  The live simulation exercises the real (failing) LLM
    path separately; this audit gives the commit workflow something real to
    commit without needing actual provider API keys."""
    print("[synthetic ai audit]")
    if AIIngestAudit.objects.filter(
        validated_output__invoice_number="SYN-INV-2026-0114"
    ).exists():
        audit = AIIngestAudit.objects.get(
            validated_output__invoice_number="SYN-INV-2026-0114"
        )
        os.makedirs(INVOICES_DIR, exist_ok=True)
        with open(os.path.join(INVOICES_DIR, "synthetic_audit_id.txt"), "w", encoding="utf-8") as fh:
            fh.write(str(audit.id))
        info("already present (id saved)")
        return
    validated = {
        "invoice_number": "SYN-INV-2026-0114",
        "invoice_date": "2026-09-20",
        "supplier_name": "SYN-MediCorp Global",
        "currency": "USD",
        "subtotal": 311.0,
        "tax": 0.0,
        "total": 311.0,
        "line_items": [
            {"description": "SYN-Amoxicillin 500mg", "quantity": 500, "unit_price": 0.42, "line_total": 210.0},
            {"description": "SYN-Ibuprofen 400mg", "quantity": 400, "unit_price": 0.11, "line_total": 44.0},
            {"description": "SYN-Metformin 850mg", "quantity": 300, "unit_price": 0.19, "line_total": 57.0},
        ],
    }
    AIIngestAudit.objects.create(
        provider="synthetic", model="synthetic-offline-v1",
        raw_output={"note": "seeded synthetic extraction for commit workflow demo"},
        validated_output=validated,
        latency_ms=1, succeeded=True, created_by=users["devadmin"],
    )
    os.makedirs(INVOICES_DIR, exist_ok=True)
    with open(os.path.join(INVOICES_DIR, "synthetic_audit_id.txt"), "w", encoding="utf-8") as fh:
        fh.write(str(audit.id))
    info(f"created successful AIIngestAudit for SYN-INV-2026-0114 (id saved)")


# ---------------------------------------------------------------------------
# invoice text files for the live upload workflow
# ---------------------------------------------------------------------------
def write_invoice_files():
    os.makedirs(INVOICES_DIR, exist_ok=True)
    files = {
        "invoice_1_medicorp.txt": INVOICE_1_TEXT,
        "invoice_2_pharmadirect.txt": INVOICE_2_TEXT,
        "invoice_3_malformed.txt": INVOICE_3_TEXT,
    }
    for fname, text in files.items():
        with open(os.path.join(INVOICES_DIR, fname), "w", encoding="utf-8") as fh:
            fh.write(text)
    info(f"wrote {len(files)} invoice text files to scratch_invoices/")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wipe", action="store_true",
                        help="delete previously seeded SYN- rows before re-seeding")
    args = parser.parse_args()

    if args.wipe:
        print("[wipe]")
        Lot.objects.filter(batch_number__startswith=PREFIX).delete()
        Product.objects.filter(name__startswith=PREFIX).delete()
        Supplier.objects.filter(name__startswith=PREFIX).delete()
        RefillReminder.objects.filter(contact__first_name__in=["Alice", "Bob", "Carla"]).filter(
            product__name__startswith=PREFIX).delete()
        Task.objects.filter(title__startswith=PREFIX).delete()
        Activity.objects.filter(subject__startswith=PREFIX).delete()
        Opportunity.objects.filter(name__startswith=PREFIX).delete()
        Campaign.objects.filter(name__startswith=PREFIX).delete()
        Lead.objects.filter(name__startswith=PREFIX).delete()
        Contact.objects.filter(first_name__in=["Alice", "Bob", "Carla", "Dmitri", "Elena"],
                               last_name__in=["Nguyen", "Okafor", "Reyes", "Ivanov", "Marsh"]).delete()
        Account.objects.filter(name__startswith=PREFIX).delete()
        Tag.objects.filter(name__startswith=PREFIX).delete()
        syn_orders = list(Order.objects.filter(supplier__name__startswith=PREFIX).values_list("id", flat=True))
        syn_audit_ids = list(AIIngestAudit.objects.filter(provider="synthetic").values_list("id", flat=True))
        ApprovalRequest.objects.filter(action_type="ORDER_SUBMIT",
                                       payload__order_id__in=[str(o) for o in syn_orders]).delete()
        ApprovalRequest.objects.filter(action_type="AI_COMMIT",
                                       payload__audit_id__in=[str(a) for a in syn_audit_ids]).delete()
        AIIngestAudit.objects.filter(provider="synthetic").delete()
        AuditLog.objects.filter(action__startswith="SYN-").delete()
        Order.objects.filter(supplier__name__startswith=PREFIX).delete()
        for u in User.objects.filter(username__in=["synsales", "synpharm", "synproc"]):
            u.delete()
        print("  wiped SYN- rows")

    users = seed_users()
    prod_objs, sup_objs = seed_catalog()
    seed_crm(users)
    seed_orders(prod_objs, sup_objs)
    seed_synthetic_audit(users)
    write_invoice_files()
    print("\nSeed complete.")


if __name__ == "__main__":
    main()
