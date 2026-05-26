# SOURCES

## 1) SAP fuel + procurement

### Real-world format researched
- SAP-style CSV exports and procurement import/export docs with plant and unit-centric fields.
- References:
  - [SAP Help: Invoice data generic CSV variants](https://help.sap.com/docs/buying-invoicing/invoicing-data-import-and-administration-guide/about-invoice-data-in-generic-variants?version=2602)
  - [SAP Procurement Admin PDF (CSV export/import patterns)](https://help.sap.com/doc/6c6aa6afc1da10149a5eec27ae2c573b/2502/en-US/ProcurementAdmin.pdf)
  - [SAP Business Accelerator Hub: I_GOODSMOVEMENTDOCUMENTDEX fields](https://api.sap.com/cdsviews/I_GOODSMOVEMENTDOCUMENTDEX/fields)

### What I learned
- Plant and unit fields are central and often require lookup/enrichment to become analyst-readable.
- CSV exports are common in onboarding phases before API access and delta extraction are available.
- Header language and naming can vary significantly by SAP configuration.

### Why sample data looks this way
- `sample_data/sap_fuel_procurement.csv` uses mixed unit styles (`L`, `gal`, `t`, `kg`), mixed date formats, and plant codes including an unknown mapping case.
- Includes both fuel-like and procurement-like lines to exercise Scope 1 and Scope 3 split.

### What would break in real deployment
- SAP repost/correction semantics need explicit upsert policy by business key.
- Non-mass procurement units (`EA`, `BOX`) need material-master conversion logic.
- True production exports can include many more movement types and joins than handled here.

## 2) Utility electricity

### Real-world format researched
- Utility bill objects and billing summaries with bill period, usage unit, tariff, and cost.
- References:
  - [UtilityAPI Bills object](https://utilityapi.com/docs/api/bills)
  - [UtilityAPI Bill blocks](https://utilityapi.com/docs/api/bills/blocks)
  - [UtilityAPI API overview](https://utilityapi.com/docs/api)

### What I learned
- Billing periods are not guaranteed to match calendar months.
- Tariff/service metadata is critical context for analysts.
- Utilities differ in detail depth; standardization layers are typically required.

### Why sample data looks this way
- `sample_data/utility_electricity.csv` uses bill start/end periods and tariff names, not monthly buckets.
- Includes a 59-day billing period row to trigger suspicion logic for unusual period length.

### What would break in real deployment
- Interval data reconciliation is not implemented.
- Time-of-use and demand charge decomposition is not modeled.
- Currency normalization and tax line-items are simplified.

## 3) Corporate travel (flights/hotels/ground)

### Real-world format researched
- SAP Concur travel-related API surfaces and itinerary-oriented objects.
- References:
  - [SAP Concur Travel Allowance v4 itinerary results](https://preview.developer.concur.com/api-reference/travelallowance/v4.travelallowance-calculationresults-endpoints.html)
  - [SAP Concur Ground Transportation Direct Connect](https://developer.concur.com/api-reference/direct-connects/ground-transportation/post-reservation-sell.html)
  - Example field convention for airport-coded trip legs: [Cybersource travel legs destination](https://developer.cybersource.com/docs/cybs/en-us/api-fields/reference/all/rest/api-fields/travel-info-aa/travel-info-legs-dest.html)

### What I learned
- Travel data is category-dependent: flights, hotels, and ground transport have different activity units.
- Distance may be missing and derivation from airport codes is a practical fallback.
- Segment-level data is more useful for emissions than expense-report totals.

### Why sample data looks this way
- `sample_data/travel_segments.json` mixes flight/hotel/ground categories.
- One flight intentionally omits distance and relies on airport code derivation.
- Ground segment uses miles to test unit conversion.

### What would break in real deployment
- Cabin class and route-specific factor accuracy is not modeled.
- Multi-leg/stopover itinerary reconstruction is simplified.
- Supplier, class-of-service, and policy metadata are not yet integrated into factor logic.
