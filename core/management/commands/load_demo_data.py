from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from core.models import Tenant
from core.services import ingest_sap_csv, ingest_travel_json, ingest_utility_csv


class Command(BaseCommand):
    help = "Load sample SAP, utility, and travel files into a tenant."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", default="acme-enterprise")
        parser.add_argument(
            "--sample-dir",
            default=str(Path("sample_data")),
            help="Directory containing sap_fuel_procurement.csv, utility_electricity.csv, travel_segments.json",
        )

    def handle(self, *args, **options):
        tenant_slug = options["tenant"]
        sample_dir = Path(options["sample_dir"])

        tenant = Tenant.objects.filter(slug=tenant_slug).first()
        if not tenant:
            raise CommandError(f"Tenant '{tenant_slug}' not found. Run seed_reference_data first.")

        sap_path = sample_dir / "sap_fuel_procurement.csv"
        utility_path = sample_dir / "utility_electricity.csv"
        travel_path = sample_dir / "travel_segments.json"
        for path in (sap_path, utility_path, travel_path):
            if not path.exists():
                raise CommandError(f"Missing sample file: {path}")

        with sap_path.open("rb") as handle:
            sap_result = ingest_sap_csv(tenant, File(handle, name=sap_path.name), initiated_by="demo-loader")
        with utility_path.open("rb") as handle:
            utility_result = ingest_utility_csv(
                tenant, File(handle, name=utility_path.name), initiated_by="demo-loader"
            )
        with travel_path.open("rb") as handle:
            travel_result = ingest_travel_json(
                tenant, File(handle, name=travel_path.name), initiated_by="demo-loader"
            )

        self.stdout.write(self.style.SUCCESS("Demo ingestion complete"))
        self.stdout.write(f"SAP: {sap_result}")
        self.stdout.write(f"Utility: {utility_result}")
        self.stdout.write(f"Travel: {travel_result}")
