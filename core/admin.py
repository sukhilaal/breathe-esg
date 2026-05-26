from django.contrib import admin

from core.models import (
    ActivityAction,
    ActivityRecord,
    ActivityRevision,
    Airport,
    IngestionBatch,
    PlantMapping,
    Tenant,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")


@admin.register(PlantMapping)
class PlantMappingAdmin(admin.ModelAdmin):
    list_display = ("tenant", "sap_plant_code", "facility_name", "country_code")
    search_fields = ("sap_plant_code", "facility_name")
    list_filter = ("tenant",)


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ("iata_code", "city", "country_code")
    search_fields = ("iata_code", "city")


@admin.register(IngestionBatch)
class IngestionBatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "source_system",
        "state",
        "row_count",
        "success_count",
        "failure_count",
        "received_at",
    )
    list_filter = ("source_system", "state", "tenant")


@admin.register(ActivityRecord)
class ActivityRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "source_system",
        "source_record_id",
        "scope",
        "category",
        "quantity_normalized",
        "unit_normalized",
        "emissions_kgco2e",
        "state",
        "suspicious",
    )
    list_filter = ("tenant", "source_system", "scope", "state", "suspicious")
    search_fields = ("source_record_id", "description", "facility_code", "facility_name")


admin.site.register(ActivityRevision)
admin.site.register(ActivityAction)

# Register your models here.
