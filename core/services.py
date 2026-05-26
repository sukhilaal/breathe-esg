import csv
import json
import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any

from dateutil import parser as date_parser
from django.db import transaction
from django.utils import timezone

from core.models import (
    ActivityRecord,
    ActivityState,
    Airport,
    BatchState,
    IngestionBatch,
    ScopeCategory,
    SourceSystem,
    Tenant,
)
from core.reference_data import EMISSION_FACTORS, SUSPICIOUS_THRESHOLDS, UNIT_ALIASES, UNIT_CONVERSIONS


SAP_FIELD_MAP = {
    "belegnummer": "document_number",
    "materialbeleg": "document_number",
    "material_document": "document_number",
    "materialdocument": "document_number",
    "item": "item_number",
    "position": "item_number",
    "werks": "plant_code",
    "plant": "plant_code",
    "buchungsdatum": "posting_date",
    "postingdate": "posting_date",
    "posting_date": "posting_date",
    "menge": "quantity",
    "quantity": "quantity",
    "meins": "unit",
    "baseunit": "unit",
    "unit": "unit",
    "material": "material_code",
    "materialnummer": "material_code",
    "materialgruppe": "material_group",
    "materialgroup": "material_group",
    "fueltype": "fuel_type",
    "warentext": "description",
    "materialtext": "description",
    "description": "description",
    "nettowert": "amount",
    "netvalue": "amount",
    "currency": "currency",
    "waehrung": "currency",
}

UTILITY_FIELD_MAP = {
    "meter_id": "meter_id",
    "meternumber": "meter_id",
    "bill_start_date": "bill_start_date",
    "bill_end_date": "bill_end_date",
    "billing_period_start": "bill_start_date",
    "billing_period_end": "bill_end_date",
    "bill_total_volume": "usage",
    "usage": "usage",
    "consumption": "usage",
    "bill_total_unit": "unit",
    "unit": "unit",
    "service_tariff": "tariff",
    "tariff": "tariff",
    "bill_total_cost": "amount",
    "amount": "amount",
    "currency": "currency",
    "site_code": "site_code",
}

TRAVEL_FIELD_MAP = {
    "trip_id": "trip_id",
    "segment_id": "segment_id",
    "category": "category",
    "travel_type": "category",
    "start_date": "start_date",
    "end_date": "end_date",
    "origin_airport": "origin_airport",
    "from_airport": "origin_airport",
    "destination_airport": "destination_airport",
    "to_airport": "destination_airport",
    "distance_km": "distance_km",
    "distance_miles": "distance_miles",
    "nights": "nights",
    "amount": "amount",
    "currency": "currency",
}

AIR_TRAVEL_TYPES = {"flight", "air", "airfare"}
GROUND_TRAVEL_TYPES = {"ground", "taxi", "car", "rail", "train"}
HOTEL_TRAVEL_TYPES = {"hotel", "lodging"}


@dataclass
class NormalizedPayload:
    source_record_id: str
    scope: str
    category: str
    subcategory: str
    activity_start: date
    activity_end: date
    quantity_original: Decimal
    unit_original: str
    quantity_normalized: Decimal
    unit_normalized: str
    facility_code: str = ""
    facility_name: str = ""
    description: str = ""
    currency: str = ""
    amount: Decimal | None = None
    travel_origin: str = ""
    travel_destination: str = ""
    travel_distance_km: Decimal | None = None
    suspicious_reasons: list[str] | None = None


class RowValidationError(Exception):
    pass


def _canonical_name(raw: str) -> str:
    return "".join(ch for ch in raw.strip().lower() if ch.isalnum() or ch == "_")


def _coerce_decimal(raw: Any, field_name: str) -> Decimal:
    if raw is None or str(raw).strip() == "":
        raise RowValidationError(f"Missing numeric value: {field_name}")
    value = str(raw).strip().replace(" ", "")
    if value.count(",") == 1 and value.count(".") == 0:
        value = value.replace(",", ".")
    elif value.count(",") > 0 and value.count(".") > 0:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise RowValidationError(f"Invalid numeric value for {field_name}: {raw}") from exc


def _coerce_date(raw: Any, field_name: str) -> date:
    if raw is None or str(raw).strip() == "":
        raise RowValidationError(f"Missing date value: {field_name}")
    try:
        parsed = date_parser.parse(str(raw), dayfirst=True)
        return parsed.date()
    except (ValueError, TypeError) as exc:
        raise RowValidationError(f"Invalid date value for {field_name}: {raw}") from exc


def _normalize_unit_label(unit: str) -> str:
    normalized = UNIT_ALIASES.get(str(unit).strip().lower(), str(unit).strip().lower())
    return normalized or "unknown"


def _normalize_quantity(quantity: Decimal, unit: str, target_unit: str | None) -> tuple[Decimal, str, str | None]:
    current_unit = _normalize_unit_label(unit)
    if not target_unit or current_unit == target_unit:
        return quantity, current_unit, None
    factor = UNIT_CONVERSIONS.get((current_unit, target_unit))
    if factor is None:
        return quantity, current_unit, f"Could not convert unit '{current_unit}' to '{target_unit}'"
    return quantity * factor, target_unit, None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> Decimal:
    radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return Decimal(str(radius_km * c)).quantize(Decimal("0.001"))


def _airport_coords() -> dict[str, tuple[float, float]]:
    data = {}
    for airport in Airport.objects.all():
        data[airport.iata_code.upper()] = (airport.latitude, airport.longitude)
    return data


def _emit_estimate(category: str, quantity: Decimal, unit: str) -> tuple[Decimal | None, Decimal | None, str]:
    factor = EMISSION_FACTORS.get((category, unit))
    if factor is None:
        return None, None, ""
    emissions = (quantity * factor).quantize(Decimal("0.000001"))
    return emissions, factor, f"kgco2e_per_{unit}"


def _flag_outlier(category: str, quantity: Decimal, unit: str, reasons: list[str]) -> None:
    threshold = SUSPICIOUS_THRESHOLDS.get((category, unit))
    if threshold and quantity > threshold:
        reasons.append(f"Quantity {quantity} {unit} exceeds threshold {threshold} {unit}")


def _translate_row(row: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    translated: dict[str, Any] = {}
    for key, value in row.items():
        canonical = _canonical_name(key)
        translated_key = mapping.get(canonical, canonical)
        translated[translated_key] = value
    return translated


def _safe_amount(raw: Any) -> Decimal | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return _coerce_decimal(raw, "amount")
    except RowValidationError:
        return None


def _scope_for_sap(category: str) -> str:
    if category in {"diesel_combustion", "gasoline_combustion"}:
        return ScopeCategory.SCOPE_1
    return ScopeCategory.SCOPE_3


def parse_sap_row(row: dict[str, Any], row_index: int, tenant: Tenant) -> NormalizedPayload:
    mapped = _translate_row(row, SAP_FIELD_MAP)
    reasons: list[str] = []
    raw_desc = str(mapped.get("description", "")).strip()
    lookup_text = " ".join(
        [
            raw_desc.lower(),
            str(mapped.get("material_group", "")).lower(),
            str(mapped.get("fuel_type", "")).lower(),
        ]
    )

    if "diesel" in lookup_text or "hsd" in lookup_text:
        category = "diesel_combustion"
        target_unit = "l"
    elif "petrol" in lookup_text or "gasoline" in lookup_text:
        category = "gasoline_combustion"
        target_unit = "l"
    else:
        category = "procurement_mass"
        target_unit = "kg"

    quantity = _coerce_decimal(mapped.get("quantity"), "quantity")
    source_unit = str(mapped.get("unit") or target_unit)
    normalized_quantity, normalized_unit, warning = _normalize_quantity(quantity, source_unit, target_unit)
    if warning:
        reasons.append(warning)

    posting_date = _coerce_date(mapped.get("posting_date"), "posting_date")
    plant_code = str(mapped.get("plant_code", "")).strip().upper()
    facility_name = ""
    if plant_code:
        plant = tenant.plant_mappings.filter(sap_plant_code=plant_code).first()
        if plant:
            facility_name = plant.facility_name
        else:
            reasons.append(f"No plant mapping found for code '{plant_code}'")

    source_record_id = str(mapped.get("document_number") or f"SAP-{row_index}").strip()
    item_number = str(mapped.get("item_number") or "").strip()
    if item_number:
        source_record_id = f"{source_record_id}-{item_number}"

    _flag_outlier(category, normalized_quantity, normalized_unit, reasons)
    if normalized_quantity < 0:
        reasons.append("Negative quantity")

    return NormalizedPayload(
        source_record_id=source_record_id,
        scope=_scope_for_sap(category),
        category=category,
        subcategory=str(mapped.get("material_group", "")).strip(),
        activity_start=posting_date,
        activity_end=posting_date,
        quantity_original=quantity,
        unit_original=source_unit,
        quantity_normalized=normalized_quantity,
        unit_normalized=normalized_unit,
        facility_code=plant_code,
        facility_name=facility_name,
        description=raw_desc,
        currency=str(mapped.get("currency", "")).strip().upper(),
        amount=_safe_amount(mapped.get("amount")),
        suspicious_reasons=reasons or None,
    )


def parse_utility_row(row: dict[str, Any], row_index: int) -> NormalizedPayload:
    mapped = _translate_row(row, UTILITY_FIELD_MAP)
    reasons: list[str] = []
    usage = _coerce_decimal(mapped.get("usage"), "usage")
    source_unit = str(mapped.get("unit") or "kwh").strip()
    normalized_usage, normalized_unit, warning = _normalize_quantity(usage, source_unit, "kwh")
    if warning:
        reasons.append(warning)

    start_date = _coerce_date(mapped.get("bill_start_date"), "bill_start_date")
    end_date = _coerce_date(mapped.get("bill_end_date"), "bill_end_date")
    if end_date < start_date:
        reasons.append("Billing end date is before start date")
    bill_days = (end_date - start_date).days
    if bill_days < 20 or bill_days > 45:
        reasons.append(f"Billing period length {bill_days} days is unusual")

    _flag_outlier("electricity", normalized_usage, normalized_unit, reasons)
    if normalized_usage < 0:
        reasons.append("Negative electricity usage")

    source_record_id = str(mapped.get("meter_id") or f"METER-{row_index}").strip()
    source_record_id = f"{source_record_id}-{start_date.isoformat()}-{end_date.isoformat()}"

    return NormalizedPayload(
        source_record_id=source_record_id,
        scope=ScopeCategory.SCOPE_2,
        category="electricity",
        subcategory=str(mapped.get("tariff", "")).strip(),
        activity_start=start_date,
        activity_end=end_date,
        quantity_original=usage,
        unit_original=source_unit,
        quantity_normalized=normalized_usage,
        unit_normalized=normalized_unit,
        facility_code=str(mapped.get("site_code", "")).strip(),
        facility_name=str(mapped.get("site_code", "")).strip(),
        description=str(mapped.get("tariff", "")).strip(),
        currency=str(mapped.get("currency", "")).strip().upper(),
        amount=_safe_amount(mapped.get("amount")),
        suspicious_reasons=reasons or None,
    )


def parse_travel_row(row: dict[str, Any], row_index: int, airport_lookup: dict[str, tuple[float, float]]) -> NormalizedPayload:
    mapped = _translate_row(row, TRAVEL_FIELD_MAP)
    reasons: list[str] = []
    category_raw = str(mapped.get("category", "flight")).strip().lower()
    if category_raw in AIR_TRAVEL_TYPES:
        category = "flight"
        unit = "km"
        target_quantity: Decimal | None = None
        if mapped.get("distance_km") not in (None, ""):
            target_quantity = _coerce_decimal(mapped.get("distance_km"), "distance_km")
        elif mapped.get("distance_miles") not in (None, ""):
            miles = _coerce_decimal(mapped.get("distance_miles"), "distance_miles")
            target_quantity, _, _ = _normalize_quantity(miles, "mi", "km")
        else:
            origin = str(mapped.get("origin_airport", "")).strip().upper()
            destination = str(mapped.get("destination_airport", "")).strip().upper()
            if origin and destination and origin in airport_lookup and destination in airport_lookup:
                origin_coords = airport_lookup[origin]
                destination_coords = airport_lookup[destination]
                target_quantity = _haversine_km(
                    origin_coords[0], origin_coords[1], destination_coords[0], destination_coords[1]
                )
            else:
                reasons.append("No distance and insufficient airport codes to derive distance")
                target_quantity = Decimal("0")
        if target_quantity and target_quantity > Decimal("0"):
            _flag_outlier(category, target_quantity, unit, reasons)
        quantity_original = target_quantity
        unit_original = "km_derived"
        quantity_normalized = target_quantity or Decimal("0")
        unit_normalized = unit
    elif category_raw in HOTEL_TRAVEL_TYPES:
        category = "hotel"
        nights = _coerce_decimal(mapped.get("nights") or 1, "nights")
        quantity_original = nights
        unit_original = "night"
        quantity_normalized = nights
        unit_normalized = "night"
    elif category_raw in GROUND_TRAVEL_TYPES:
        category = "ground_transport"
        if mapped.get("distance_km") not in (None, ""):
            distance = _coerce_decimal(mapped.get("distance_km"), "distance_km")
            quantity_original = distance
            unit_original = "km"
            quantity_normalized = distance
            unit_normalized = "km"
        else:
            miles = _coerce_decimal(mapped.get("distance_miles"), "distance_miles")
            normalized_distance, normalized_unit, warning = _normalize_quantity(miles, "mi", "km")
            if warning:
                reasons.append(warning)
            quantity_original = miles
            unit_original = "mi"
            quantity_normalized = normalized_distance
            unit_normalized = normalized_unit
        _flag_outlier(category, quantity_normalized, unit_normalized, reasons)
    else:
        raise RowValidationError(f"Unsupported travel category '{category_raw}'")

    source_record_id = str(mapped.get("segment_id") or mapped.get("trip_id") or f"TRAVEL-{row_index}").strip()
    start_date = _coerce_date(mapped.get("start_date"), "start_date")
    end_date = _coerce_date(mapped.get("end_date") or mapped.get("start_date"), "end_date")
    if end_date < start_date:
        reasons.append("Travel segment end date is before start date")

    origin = str(mapped.get("origin_airport", "")).strip().upper()
    destination = str(mapped.get("destination_airport", "")).strip().upper()
    distance_km = quantity_normalized if category in {"flight", "ground_transport"} else None

    return NormalizedPayload(
        source_record_id=source_record_id,
        scope=ScopeCategory.SCOPE_3,
        category=category,
        subcategory=category_raw,
        activity_start=start_date,
        activity_end=end_date,
        quantity_original=quantity_original,
        unit_original=unit_original,
        quantity_normalized=quantity_normalized,
        unit_normalized=unit_normalized,
        description=category_raw,
        currency=str(mapped.get("currency", "")).strip().upper(),
        amount=_safe_amount(mapped.get("amount")),
        travel_origin=origin,
        travel_destination=destination,
        travel_distance_km=distance_km,
        suspicious_reasons=reasons or None,
    )


def _build_activity(
    tenant: Tenant,
    batch: IngestionBatch,
    source_system: str,
    payload: NormalizedPayload,
    source_row: dict[str, Any],
) -> tuple[ActivityRecord, bool]:
    reasons = list(payload.suspicious_reasons or [])
    emissions, factor_value, factor_unit = _emit_estimate(
        payload.category,
        payload.quantity_normalized,
        payload.unit_normalized,
    )
    state = ActivityState.PENDING
    suspicious = bool(reasons)
    existing = ActivityRecord.objects.filter(
        tenant=tenant,
        source_system=source_system,
        source_record_id=payload.source_record_id,
    ).first()
    if existing and existing.state == ActivityState.LOCKED:
        raise RowValidationError("Record is locked for audit and cannot be overwritten")

    activity, created = ActivityRecord.objects.update_or_create(
        tenant=tenant,
        source_system=source_system,
        source_record_id=payload.source_record_id,
        defaults={
            "batch": batch,
            "scope": payload.scope,
            "category": payload.category,
            "subcategory": payload.subcategory,
            "activity_start": payload.activity_start,
            "activity_end": payload.activity_end,
            "description": payload.description,
            "facility_code": payload.facility_code,
            "facility_name": payload.facility_name,
            "quantity_original": payload.quantity_original,
            "unit_original": payload.unit_original,
            "quantity_normalized": payload.quantity_normalized,
            "unit_normalized": payload.unit_normalized,
            "currency": payload.currency,
            "amount": payload.amount,
            "travel_origin": payload.travel_origin,
            "travel_destination": payload.travel_destination,
            "travel_distance_km": payload.travel_distance_km,
            "emission_factor_value": factor_value,
            "emission_factor_unit": factor_unit,
            "emissions_kgco2e": emissions,
            "suspicious": suspicious,
            "suspicion_reasons": reasons,
            "state": state,
            "source_payload": source_row,
        },
    )
    return activity, created


def _decode_csv(uploaded_file) -> list[dict[str, Any]]:
    raw_bytes = uploaded_file.read()
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(StringIO(text))
    return [row for row in reader if any(str(value).strip() for value in row.values())]


def _decode_json(uploaded_file) -> list[dict[str, Any]]:
    raw_bytes = uploaded_file.read()
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    parsed = json.loads(text)
    if isinstance(parsed, dict):
        if "records" in parsed and isinstance(parsed["records"], list):
            return parsed["records"]
        raise RowValidationError("Travel JSON payload must be a list or include a 'records' list")
    if not isinstance(parsed, list):
        raise RowValidationError("Travel JSON payload must be an array")
    return parsed


def ingest_sap_csv(tenant: Tenant, uploaded_file, initiated_by: str = "system") -> dict[str, Any]:
    return _ingest_rows(
        tenant=tenant,
        source_system=SourceSystem.SAP,
        rows=_decode_csv(uploaded_file),
        file_name=uploaded_file.name,
        initiated_by=initiated_by,
    )


def ingest_utility_csv(tenant: Tenant, uploaded_file, initiated_by: str = "system") -> dict[str, Any]:
    return _ingest_rows(
        tenant=tenant,
        source_system=SourceSystem.UTILITY,
        rows=_decode_csv(uploaded_file),
        file_name=uploaded_file.name,
        initiated_by=initiated_by,
    )


def ingest_travel_json(tenant: Tenant, uploaded_file, initiated_by: str = "system") -> dict[str, Any]:
    return _ingest_rows(
        tenant=tenant,
        source_system=SourceSystem.TRAVEL,
        rows=_decode_json(uploaded_file),
        file_name=uploaded_file.name,
        initiated_by=initiated_by,
    )


def _ingest_rows(
    tenant: Tenant,
    source_system: str,
    rows: list[dict[str, Any]],
    file_name: str,
    initiated_by: str,
) -> dict[str, Any]:
    with transaction.atomic():
        batch = IngestionBatch.objects.create(
            tenant=tenant,
            source_system=source_system,
            initiated_by=initiated_by,
            file_name=file_name,
            row_count=len(rows),
            state=BatchState.RECEIVED,
        )
        errors: list[dict[str, Any]] = []
        success_count = 0
        airport_lookup = _airport_coords() if source_system == SourceSystem.TRAVEL else {}
        parser = {
            SourceSystem.SAP: lambda row, idx: parse_sap_row(row, idx, tenant),
            SourceSystem.UTILITY: lambda row, idx: parse_utility_row(row, idx),
            SourceSystem.TRAVEL: lambda row, idx: parse_travel_row(row, idx, airport_lookup),
        }[source_system]

        for idx, row in enumerate(rows, start=1):
            try:
                normalized = parser(row, idx)
                _build_activity(tenant, batch, source_system, normalized, row)
                success_count += 1
            except Exception as exc:
                errors.append({"row": idx, "error": str(exc)})

        batch.success_count = success_count
        batch.failure_count = len(errors)
        batch.state = BatchState.PROCESSED if not errors else BatchState.FAILED
        batch.processed_at = timezone.now()
        if errors:
            batch.notes = json.dumps(errors[:20])
        batch.save(
            update_fields=[
                "success_count",
                "failure_count",
                "state",
                "processed_at",
                "notes",
            ]
        )

    return {
        "batch_id": batch.id,
        "source_system": str(source_system),
        "row_count": batch.row_count,
        "success_count": batch.success_count,
        "failure_count": batch.failure_count,
        "errors": errors[:20],
    }
