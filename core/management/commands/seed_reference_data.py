from django.core.management.base import BaseCommand

from core.models import Airport, PlantMapping, Tenant
from core.reference_data import AIRPORTS


class Command(BaseCommand):
    help = "Seed default tenant and reference lookup tables."

    def handle(self, *args, **options):
        tenant, created = Tenant.objects.get_or_create(
            slug="acme-enterprise",
            defaults={"name": "ACME Enterprise"},
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created default tenant acme-enterprise"))
        else:
            self.stdout.write("Default tenant already exists")

        plant_defaults = [
            ("1000", "Bangalore Blending Plant", "IN"),
            ("1100", "Chennai Packaging Plant", "IN"),
            ("2000", "Mumbai Distribution Hub", "IN"),
        ]
        for code, facility, country in plant_defaults:
            PlantMapping.objects.get_or_create(
                tenant=tenant,
                sap_plant_code=code,
                defaults={"facility_name": facility, "country_code": country},
            )

        airport_count = 0
        for airport in AIRPORTS:
            _, airport_created = Airport.objects.get_or_create(
                iata_code=airport["iata_code"],
                defaults={
                    "city": airport["city"],
                    "country_code": airport["country_code"],
                    "latitude": airport["latitude"],
                    "longitude": airport["longitude"],
                },
            )
            if airport_created:
                airport_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded lookup data. New airports: {airport_count}"))
