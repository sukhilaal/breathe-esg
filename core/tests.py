from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from core.management.commands.seed_reference_data import Command as SeedCommand
from core.models import ActivityRecord, ActivityState, Tenant
from core.services import ingest_sap_csv, ingest_travel_json

class IngestionTests(TestCase):
    def setUp(self):
        SeedCommand().handle()
        self.tenant = Tenant.objects.get(slug="acme-enterprise")

    def test_ingest_sap_csv_normalizes_gallons(self):
        csv_content = (
            "Belegnummer,Item,Werk,Buchungsdatum,Materialgruppe,Warentext,Menge,MEINS\n"
            "12345,10,1000,15.01.2026,FUEL,Petrol,100,gal\n"
        )
        file = SimpleUploadedFile("sap.csv", csv_content.encode("utf-8"), content_type="text/csv")

        result = ingest_sap_csv(self.tenant, file, initiated_by="tester")
        self.assertEqual(result["success_count"], 1)

        record = ActivityRecord.objects.get(source_record_id="12345-10")
        self.assertEqual(record.category, "gasoline_combustion")
        self.assertEqual(record.unit_normalized, "l")
        self.assertEqual(record.quantity_normalized, Decimal("378.541000"))

    def test_ingest_travel_json_derives_distance_from_airports(self):
        payload = """
        [
          {
            "trip_id": "T-1",
            "segment_id": "S-1",
            "category": "flight",
            "start_date": "2026-01-01",
            "end_date": "2026-01-01",
            "origin_airport": "BLR",
            "destination_airport": "DEL"
          }
        ]
        """
        file = SimpleUploadedFile("travel.json", payload.encode("utf-8"), content_type="application/json")

        result = ingest_travel_json(self.tenant, file, initiated_by="tester")
        self.assertEqual(result["success_count"], 1)

        record = ActivityRecord.objects.get(source_record_id="S-1")
        self.assertEqual(record.category, "flight")
        self.assertGreater(record.travel_distance_km, Decimal("1500"))

    def test_locked_record_cannot_be_overwritten_on_reingest(self):
        csv_content = (
            "Belegnummer,Item,Werk,Buchungsdatum,Materialgruppe,Warentext,Menge,MEINS\n"
            "12345,10,1000,15.01.2026,FUEL,Diesel,1000,l\n"
        )
        file_1 = SimpleUploadedFile("sap.csv", csv_content.encode("utf-8"), content_type="text/csv")
        ingest_sap_csv(self.tenant, file_1, initiated_by="tester")

        record = ActivityRecord.objects.get(source_record_id="12345-10")
        record.state = ActivityState.LOCKED
        record.save(update_fields=["state"])

        file_2 = SimpleUploadedFile("sap.csv", csv_content.encode("utf-8"), content_type="text/csv")
        result = ingest_sap_csv(self.tenant, file_2, initiated_by="tester")
        self.assertEqual(result["failure_count"], 1)
