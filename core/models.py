from django.db import models


class SourceSystem(models.TextChoices):
    SAP = "sap", "SAP Fuel & Procurement"
    UTILITY = "utility", "Utility Electricity"
    TRAVEL = "travel", "Corporate Travel"


class ActivityState(models.TextChoices):
    PENDING = "pending", "Pending Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    LOCKED = "locked", "Locked for Audit"


class BatchState(models.TextChoices):
    RECEIVED = "received", "Received"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"


class ScopeCategory(models.TextChoices):
    SCOPE_1 = "scope_1", "Scope 1"
    SCOPE_2 = "scope_2", "Scope 2"
    SCOPE_3 = "scope_3", "Scope 3"


class ActionType(models.TextChoices):
    APPROVE = "approve", "Approve"
    REJECT = "reject", "Reject"
    LOCK = "lock", "Lock"
    EDIT = "edit", "Edit"


class Tenant(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class PlantMapping(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="plant_mappings")
    sap_plant_code = models.CharField(max_length=20)
    facility_name = models.CharField(max_length=200)
    country_code = models.CharField(max_length=2, default="IN")

    class Meta:
        unique_together = ("tenant", "sap_plant_code")

    def __str__(self) -> str:
        return f"{self.tenant.slug}:{self.sap_plant_code}"


class Airport(models.Model):
    iata_code = models.CharField(max_length=3, unique=True)
    city = models.CharField(max_length=120)
    country_code = models.CharField(max_length=2)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self) -> str:
        return self.iata_code


class IngestionBatch(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="batches")
    source_system = models.CharField(max_length=20, choices=SourceSystem.choices)
    source_label = models.CharField(max_length=120, blank=True)
    source_reference = models.CharField(max_length=120, blank=True)
    initiated_by = models.CharField(max_length=120, default="system")
    state = models.CharField(max_length=20, choices=BatchState.choices, default=BatchState.RECEIVED)
    file_name = models.CharField(max_length=260, blank=True)
    row_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-received_at",)


class ActivityRecord(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="activities")
    batch = models.ForeignKey(
        IngestionBatch,
        on_delete=models.SET_NULL,
        related_name="activities",
        null=True,
        blank=True,
    )
    source_system = models.CharField(max_length=20, choices=SourceSystem.choices)
    source_record_id = models.CharField(max_length=120)
    source_payload = models.JSONField(default=dict)

    scope = models.CharField(max_length=20, choices=ScopeCategory.choices)
    category = models.CharField(max_length=64)
    subcategory = models.CharField(max_length=64, blank=True)
    activity_start = models.DateField()
    activity_end = models.DateField()
    description = models.CharField(max_length=300, blank=True)

    facility_code = models.CharField(max_length=64, blank=True)
    facility_name = models.CharField(max_length=200, blank=True)

    quantity_original = models.DecimalField(max_digits=20, decimal_places=6)
    unit_original = models.CharField(max_length=40)
    quantity_normalized = models.DecimalField(max_digits=20, decimal_places=6)
    unit_normalized = models.CharField(max_length=40)

    currency = models.CharField(max_length=3, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    travel_origin = models.CharField(max_length=3, blank=True)
    travel_destination = models.CharField(max_length=3, blank=True)
    travel_distance_km = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)

    emission_factor_value = models.DecimalField(max_digits=16, decimal_places=8, null=True, blank=True)
    emission_factor_unit = models.CharField(max_length=40, blank=True)
    emissions_kgco2e = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)

    state = models.CharField(max_length=20, choices=ActivityState.choices, default=ActivityState.PENDING)
    suspicious = models.BooleanField(default=False)
    suspicion_reasons = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        unique_together = ("tenant", "source_system", "source_record_id")


class ActivityRevision(models.Model):
    activity = models.ForeignKey(ActivityRecord, on_delete=models.CASCADE, related_name="revisions")
    actor = models.CharField(max_length=120, default="system")
    note = models.CharField(max_length=240, blank=True)
    before_state = models.JSONField(default=dict)
    after_state = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class ActivityAction(models.Model):
    activity = models.ForeignKey(ActivityRecord, on_delete=models.CASCADE, related_name="actions")
    action = models.CharField(max_length=20, choices=ActionType.choices)
    actor = models.CharField(max_length=120, default="system")
    comment = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
