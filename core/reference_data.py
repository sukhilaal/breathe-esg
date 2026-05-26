"""Reference values used by the prototype normalizer."""

from decimal import Decimal

AIRPORTS = [
    {"iata_code": "BLR", "city": "Bengaluru", "country_code": "IN", "latitude": 13.1986, "longitude": 77.7066},
    {"iata_code": "DEL", "city": "Delhi", "country_code": "IN", "latitude": 28.5562, "longitude": 77.1000},
    {"iata_code": "BOM", "city": "Mumbai", "country_code": "IN", "latitude": 19.0896, "longitude": 72.8656},
    {"iata_code": "HYD", "city": "Hyderabad", "country_code": "IN", "latitude": 17.2403, "longitude": 78.4294},
    {"iata_code": "MAA", "city": "Chennai", "country_code": "IN", "latitude": 12.9941, "longitude": 80.1709},
    {"iata_code": "SIN", "city": "Singapore", "country_code": "SG", "latitude": 1.3644, "longitude": 103.9915},
    {"iata_code": "DXB", "city": "Dubai", "country_code": "AE", "latitude": 25.2532, "longitude": 55.3657},
    {"iata_code": "LHR", "city": "London", "country_code": "GB", "latitude": 51.4700, "longitude": -0.4543},
    {"iata_code": "JFK", "city": "New York", "country_code": "US", "latitude": 40.6413, "longitude": -73.7781},
    {"iata_code": "SFO", "city": "San Francisco", "country_code": "US", "latitude": 37.6213, "longitude": -122.3790},
    {"iata_code": "FRA", "city": "Frankfurt", "country_code": "DE", "latitude": 50.0379, "longitude": 8.5622},
]

UNIT_ALIASES = {
    "l": "l",
    "lt": "l",
    "ltr": "l",
    "liter": "l",
    "litre": "l",
    "gal": "gal",
    "gallon": "gal",
    "gallons": "gal",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "ton": "t",
    "tons": "t",
    "tonne": "t",
    "tonnes": "t",
    "t": "t",
    "kwh": "kwh",
    "mwh": "mwh",
    "wh": "wh",
    "km": "km",
    "mi": "mi",
    "mile": "mi",
    "miles": "mi",
    "night": "night",
    "nights": "night",
}

UNIT_CONVERSIONS = {
    ("gal", "l"): Decimal("3.78541"),
    ("t", "kg"): Decimal("1000"),
    ("mwh", "kwh"): Decimal("1000"),
    ("wh", "kwh"): Decimal("0.001"),
    ("mi", "km"): Decimal("1.60934"),
}

EMISSION_FACTORS = {
    ("electricity", "kwh"): Decimal("0.708"),  # India CEA-grid style proxy
    ("diesel_combustion", "l"): Decimal("2.680"),
    ("gasoline_combustion", "l"): Decimal("2.310"),
    ("procurement_mass", "kg"): Decimal("1.200"),
    ("flight", "km"): Decimal("0.150"),
    ("hotel", "night"): Decimal("15.000"),
    ("ground_transport", "km"): Decimal("0.180"),
}

SUSPICIOUS_THRESHOLDS = {
    ("electricity", "kwh"): Decimal("200000"),
    ("diesel_combustion", "l"): Decimal("100000"),
    ("gasoline_combustion", "l"): Decimal("100000"),
    ("procurement_mass", "kg"): Decimal("500000"),
    ("flight", "km"): Decimal("15000"),
    ("ground_transport", "km"): Decimal("2000"),
}
