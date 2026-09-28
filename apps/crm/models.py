from __future__ import annotations
import uuid
from django.conf import settings
from django.db import models


class Tag(models.Model):
    """Segment label for contacts/accounts (e.g. 'diabetes', 'tier-1-hospital')."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=64, unique=True)
    color = models.CharField(max_length=16, default="accent")

    def __str__(self):
        return self.name


class Account(models.Model):
    """An organization: hospital, clinic, wholesale buyer, pharmacy chain."""
    TYPES = [
        ("HOSPITAL", "Hospital"),
        ("CLINIC", "Clinic"),
        ("WHOLESALE", "Wholesale buyer"),
        ("CHAIN", "Pharmacy chain"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=16, choices=TYPES, default="CLINIC")
    billing_address = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="owned_accounts")
    tags = models.ManyToManyField(Tag, blank=True, related_name="accounts")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["name"]), models.Index(fields=["account_type"])]

    def __str__(self):
        return self.name


class Contact(models.Model):
    """A person: patient, prescriber, or buyer contact."""
    TYPES = [
        ("PATIENT", "Patient"),
        ("PRESCRIBER", "Prescriber"),
        ("BUYER", "Buyer"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact_type = models.CharField(max_length=12, choices=TYPES, default="PATIENT")
    first_name = models.CharField(max_length=128)
    last_name = models.CharField(max_length=128)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=32, null=True, blank=True)
    mrn = models.CharField(max_length=64, null=True, blank=True)
    account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="contacts")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="owned_contacts")
    tags = models.ManyToManyField(Tag, blank=True, related_name="contacts")
    consent_marketing = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["contact_type"]),
            models.Index(fields=["mrn"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_contact_type_display()})"


class Lead(models.Model):
    STATUS = [
        ("NEW", "New"),
        ("CONTACTED", "Contacted"),
        ("QUALIFIED", "Qualified"),
        ("UNQUALIFIED", "Unqualified"),
        ("CONVERTED", "Converted"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    source = models.CharField(max_length=64, null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="NEW")
    est_value = models.FloatField(default=0.0)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="owned_leads")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class PipelineStage(models.TextChoices):
    QUALIFICATION = "QUALIFICATION", "Qualification"
    PROPOSAL = "PROPOSAL", "Proposal"
    NEGOTIATION = "NEGOTIATION", "Negotiation"
    WON = "WON", "Won"
    LOST = "LOST", "Lost"


class Opportunity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="opportunities")
    stage = models.CharField(max_length=16, choices=PipelineStage.choices, default=PipelineStage.QUALIFICATION)
    amount = models.FloatField(default=0.0)
    probability = models.PositiveIntegerField(default=10)
    expected_close_date = models.DateField(null=True, blank=True)
    lost_reason = models.CharField(max_length=255, null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="owned_opportunities")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["stage"]),
            models.Index(fields=["expected_close_date"]),
        ]

    def __str__(self):
        return f"{self.name} — {self.get_stage_display()}"


class Activity(models.Model):
    """Interaction log attachable to a contact, account, or opportunity."""
    TYPES = [
        ("CALL", "Call"),
        ("EMAIL", "Email"),
        ("MEETING", "Meeting"),
        ("NOTE", "Note"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity_type = models.CharField(max_length=8, choices=TYPES)
    subject = models.CharField(max_length=255)
    body = models.TextField(null=True, blank=True)
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.CASCADE, related_name="activities")
    account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.CASCADE, related_name="activities")
    opportunity = models.ForeignKey(Opportunity, null=True, blank=True, on_delete=models.CASCADE, related_name="activities")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["created_at"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_activity_type_display()}: {self.subject}"


class Task(models.Model):
    STATUS = [("OPEN", "Open"), ("DONE", "Done")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    due_date = models.DateField()
    reminder_sent = models.BooleanField(default=False)
    status = models.CharField(max_length=8, choices=STATUS, default="OPEN")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="tasks")
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.CASCADE)
    opportunity = models.ForeignKey(Opportunity, null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        indexes = [models.Index(fields=["due_date", "status"])]

    def __str__(self):
        return f"{self.title} — {'Done' if self.status == 'DONE' else 'Due ' + str(self.due_date)}"


class Campaign(models.Model):
    TYPES = [
        ("REFILL", "Refill drive"),
        ("AWARENESS", "Health awareness"),
        ("PROMO", "Promotion"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    campaign_type = models.CharField(max_length=12, choices=TYPES)
    target_tags = models.ManyToManyField(Tag, blank=True, related_name="campaigns")
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_campaign_type_display()})"


class RefillReminder(models.Model):
    """Recurring-medication follow-up for a patient contact."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="refills")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE)
    interval_days = models.PositiveIntegerField(default=30)
    next_due_date = models.DateField()
    active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["next_due_date", "active"])]

    def __str__(self):
        return f"Refill for {self.contact} — {self.product.name}"
