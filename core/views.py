from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.views import APIView

from core.models import ActivityAction, ActivityRecord, ActivityRevision, IngestionBatch, Tenant
from core.serializers import (
    ActivityActionSerializer,
    ActivityRecordSerializer,
    ActivityUpdateSerializer,
    TenantSerializer,
)
from core.services import ingest_sap_csv, ingest_travel_json, ingest_utility_csv


def health(_request):
    return JsonResponse({"status": "ok"})


def _tenant_or_404(slug: str) -> Tenant:
    return get_object_or_404(Tenant, slug=slug)


class TenantListCreateView(APIView):
    def get(self, request):
        return JsonResponse({"results": TenantSerializer(Tenant.objects.all(), many=True).data})

    def post(self, request):
        serializer = TenantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        return JsonResponse(TenantSerializer(tenant).data, status=status.HTTP_201_CREATED)


class SapIngestView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        tenant_slug = request.data.get("tenant_slug")
        upload = request.FILES.get("file")
        if not tenant_slug or not upload:
            return JsonResponse({"error": "tenant_slug and file are required."}, status=400)
        tenant = _tenant_or_404(tenant_slug)
        result = ingest_sap_csv(tenant, upload, initiated_by=request.data.get("actor", "analyst"))
        return JsonResponse(result, status=201)


class UtilityIngestView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        tenant_slug = request.data.get("tenant_slug")
        upload = request.FILES.get("file")
        if not tenant_slug or not upload:
            return JsonResponse({"error": "tenant_slug and file are required."}, status=400)
        tenant = _tenant_or_404(tenant_slug)
        result = ingest_utility_csv(tenant, upload, initiated_by=request.data.get("actor", "analyst"))
        return JsonResponse(result, status=201)


class TravelIngestView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        tenant_slug = request.data.get("tenant_slug")
        upload = request.FILES.get("file")
        if not tenant_slug or not upload:
            return JsonResponse({"error": "tenant_slug and file are required."}, status=400)
        tenant = _tenant_or_404(tenant_slug)
        result = ingest_travel_json(tenant, upload, initiated_by=request.data.get("actor", "analyst"))
        return JsonResponse(result, status=201)


class DashboardSummaryView(APIView):
    def get(self, request):
        tenant_slug = request.GET.get("tenant_slug")
        tenant = _tenant_or_404(tenant_slug) if tenant_slug else None

        activities = ActivityRecord.objects.all()
        batches = IngestionBatch.objects.all()
        if tenant:
            activities = activities.filter(tenant=tenant)
            batches = batches.filter(tenant=tenant)

        state_counts = {row["state"]: row["count"] for row in activities.values("state").annotate(count=Count("id"))}
        source_counts = {
            row["source_system"]: row["count"] for row in activities.values("source_system").annotate(count=Count("id"))
        }
        scope_counts = {row["scope"]: row["count"] for row in activities.values("scope").annotate(count=Count("id"))}
        suspicious_count = activities.filter(suspicious=True).count()
        emissions_total = activities.aggregate(total=Sum("emissions_kgco2e")).get("total") or 0

        recent_batches = list(
            batches.values(
                "id",
                "source_system",
                "state",
                "row_count",
                "success_count",
                "failure_count",
                "file_name",
                "received_at",
            )[:10]
        )

        return JsonResponse(
            {
                "state_counts": state_counts,
                "source_counts": source_counts,
                "scope_counts": scope_counts,
                "suspicious_count": suspicious_count,
                "emissions_total_kgco2e": emissions_total,
                "recent_batches": recent_batches,
            }
        )


class ActivityListView(APIView):
    def get(self, request):
        tenant_slug = request.GET.get("tenant_slug")
        queryset = ActivityRecord.objects.select_related("tenant").all()
        if tenant_slug:
            queryset = queryset.filter(tenant__slug=tenant_slug)

        state = request.GET.get("state")
        if state:
            queryset = queryset.filter(state=state)

        source = request.GET.get("source_system")
        if source:
            queryset = queryset.filter(source_system=source)

        suspicious = request.GET.get("suspicious")
        if suspicious in {"true", "false"}:
            queryset = queryset.filter(suspicious=(suspicious == "true"))

        search = request.GET.get("search")
        if search:
            queryset = queryset.filter(description__icontains=search)

        limit = int(request.GET.get("limit", 200))
        records = queryset[:limit]
        serializer = ActivityRecordSerializer(records, many=True)
        return JsonResponse({"results": serializer.data})


class ActivityDetailView(APIView):
    def get_object(self, activity_id: int) -> ActivityRecord:
        return get_object_or_404(ActivityRecord, id=activity_id)

    def get(self, request, activity_id: int):
        record = self.get_object(activity_id)
        return JsonResponse(ActivityRecordSerializer(record).data)

    def patch(self, request, activity_id: int):
        record = self.get_object(activity_id)
        serializer = ActivityUpdateSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return JsonResponse(ActivityRecordSerializer(updated).data)


class ActivityActionView(APIView):
    def post(self, request, activity_id: int):
        record = get_object_or_404(ActivityRecord, id=activity_id)
        serializer = ActivityActionSerializer(data=request.data, context={"instance": record})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return JsonResponse(ActivityRecordSerializer(updated).data)


class ActivityAuditTrailView(APIView):
    def get(self, request, activity_id: int):
        revisions = list(
            ActivityRevision.objects.filter(activity_id=activity_id).values(
                "id", "actor", "note", "before_state", "after_state", "created_at"
            )
        )
        actions = list(
            ActivityAction.objects.filter(activity_id=activity_id).values(
                "id", "action", "actor", "comment", "created_at"
            )
        )
        return JsonResponse({"revisions": revisions, "actions": actions})
