from rest_framework import serializers

from core.models import ActivityAction, ActivityRecord, ActivityRevision, ActivityState, Tenant


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ("id", "name", "slug")


class ActivityRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityRecord
        fields = (
            "id",
            "tenant_id",
            "batch_id",
            "source_system",
            "source_record_id",
            "scope",
            "category",
            "subcategory",
            "activity_start",
            "activity_end",
            "description",
            "facility_code",
            "facility_name",
            "quantity_original",
            "unit_original",
            "quantity_normalized",
            "unit_normalized",
            "currency",
            "amount",
            "travel_origin",
            "travel_destination",
            "travel_distance_km",
            "emission_factor_value",
            "emission_factor_unit",
            "emissions_kgco2e",
            "state",
            "suspicious",
            "suspicion_reasons",
            "source_payload",
            "created_at",
            "updated_at",
        )


class ActivityUpdateSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(write_only=True, required=False, default="analyst")
    note = serializers.CharField(write_only=True, required=False, default="")

    class Meta:
        model = ActivityRecord
        fields = (
            "quantity_normalized",
            "unit_normalized",
            "amount",
            "description",
            "facility_code",
            "facility_name",
            "actor",
            "note",
        )

    def validate(self, attrs):
        instance = self.instance
        if instance and instance.state == ActivityState.LOCKED:
            raise serializers.ValidationError("Locked records cannot be edited.")
        return attrs

    def update(self, instance, validated_data):
        actor = validated_data.pop("actor", "analyst")
        note = validated_data.pop("note", "")
        before = {
            "quantity_normalized": str(instance.quantity_normalized),
            "unit_normalized": instance.unit_normalized,
            "amount": str(instance.amount) if instance.amount is not None else None,
            "description": instance.description,
            "facility_code": instance.facility_code,
            "facility_name": instance.facility_name,
        }

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.state = ActivityState.PENDING
        instance.save()

        after = {
            "quantity_normalized": str(instance.quantity_normalized),
            "unit_normalized": instance.unit_normalized,
            "amount": str(instance.amount) if instance.amount is not None else None,
            "description": instance.description,
            "facility_code": instance.facility_code,
            "facility_name": instance.facility_name,
        }
        ActivityRevision.objects.create(
            activity=instance,
            actor=actor,
            note=note or "Edited by analyst",
            before_state=before,
            after_state=after,
        )
        ActivityAction.objects.create(
            activity=instance,
            action="edit",
            actor=actor,
            comment=note or "",
        )
        return instance


class ActivityActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject", "lock"])
    actor = serializers.CharField(required=False, default="analyst")
    comment = serializers.CharField(required=False, default="", allow_blank=True)

    def validate(self, attrs):
        instance: ActivityRecord = self.context["instance"]
        action = attrs["action"]
        if instance.state == ActivityState.LOCKED and action != "lock":
            raise serializers.ValidationError("Locked records cannot be changed.")
        if action == "lock" and instance.state != ActivityState.APPROVED:
            raise serializers.ValidationError("Only approved rows can be locked.")
        return attrs

    def save(self, **kwargs):
        instance: ActivityRecord = self.context["instance"]
        action = self.validated_data["action"]
        actor = self.validated_data.get("actor", "analyst")
        comment = self.validated_data.get("comment", "")

        if action == "approve":
            instance.state = ActivityState.APPROVED
        elif action == "reject":
            instance.state = ActivityState.REJECTED
        elif action == "lock":
            instance.state = ActivityState.LOCKED
        instance.save(update_fields=["state", "updated_at"])

        ActivityAction.objects.create(activity=instance, action=action, actor=actor, comment=comment)
        return instance
