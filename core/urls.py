from django.urls import path

from core.views import (
    ActivityActionView,
    ActivityAuditTrailView,
    ActivityDetailView,
    ActivityListView,
    DashboardSummaryView,
    SapIngestView,
    TenantListCreateView,
    TravelIngestView,
    UtilityIngestView,
    health,
)

urlpatterns = [
    path("health/", health, name="health"),
    path("tenants/", TenantListCreateView.as_view(), name="tenants"),
    path("ingest/sap/", SapIngestView.as_view(), name="ingest-sap"),
    path("ingest/utility/", UtilityIngestView.as_view(), name="ingest-utility"),
    path("ingest/travel/", TravelIngestView.as_view(), name="ingest-travel"),
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("activities/", ActivityListView.as_view(), name="activities"),
    path("activities/<int:activity_id>/", ActivityDetailView.as_view(), name="activity-detail"),
    path("activities/<int:activity_id>/action/", ActivityActionView.as_view(), name="activity-action"),
    path("activities/<int:activity_id>/audit/", ActivityAuditTrailView.as_view(), name="activity-audit"),
]
