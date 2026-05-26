# DECISIONS

## 1) SAP ingestion mode
Decision: File upload of SAP-exported flat files (CSV), not live OData/BAPI pull.

Why:
- In enterprise onboarding, exports are often the fastest integration bridge when SAP connectivity and IAM are pending.
- CSV reflects the assignment constraints (messy headers, inconsistent units, cryptic plant codes, mixed date formats).
- Supports both English and German-like headers using a canonical mapping layer.

Subset handled:
- Material/fuel and procurement-like line items with posting date, quantity, unit, plant, and optional amount/currency.

Ignored for prototype:
- Deep SAP document graph joins (movement types, valuation classes, MM/FI reconciliation).
- Delta extraction via SAP change pointers.

PM question I would ask:
- Should SAP ingestion be one-way append-only, or should corrected SAP reposts supersede prior records by business key?

## 2) Utility ingestion mode
Decision: Portal/API-style electricity bill export CSV upload.

Why:
- Facilities teams commonly export bill summaries from utility portals or an aggregator export.
- The shape naturally includes bill start/end period, tariff, and usage unit, which supports period-aware normalization.

Subset handled:
- Electricity bills with billing period start/end, usage, unit, tariff, and bill amount.

Ignored for prototype:
- Interval reads (15-min/hourly), complex TOU line item decomposition, demand ratchets.

PM question I would ask:
- Do we need bill-level audit only, or full interval reconciliation against meter data?

## 3) Travel ingestion mode
Decision: JSON payload representing travel segments from a corporate platform export/API pull.

Why:
- Travel tools often expose itinerary/segment objects via API; JSON preserves categorical differences cleanly.
- Supports the realistic gap where distance is missing for flights and must be derived from airport codes.

Subset handled:
- Flight, hotel, and ground segments with dates, optional distance, and optional cost.
- Flight distance derivation using airport lookup and Haversine when not supplied.

Ignored for prototype:
- Cabin class radiative forcing multipliers, multi-leg itinerary chaining, rail country-specific factors.

PM question I would ask:
- Should upstream booking class and fare class be mandatory for aviation factor precision?

## 4) Multi-tenancy model
Decision: Single shared schema with tenant foreign keys.

Why:
- Fast to build and reason about in a 4-day prototype.
- Clear query-level partitioning and simple migration path to row-level policies later.

Ignored for prototype:
- Per-tenant database isolation, tenant-specific encryption keys, SSO entitlements.

PM question I would ask:
- What tenancy isolation level is expected for the first production customers?

## 5) Review workflow states
Decision: `pending -> approved/rejected -> locked`.

Why:
- Mirrors analyst review and audit freeze requirements.
- Enforces immutability after lock.

Ignored for prototype:
- Multi-step approvals, reviewer assignment queues, SLA timers.

PM question I would ask:
- Is one analyst approval sufficient, or do we need dual control before lock?

## 6) Emissions calculation strategy
Decision: Store normalized activity and an estimated factor-driven CO2e value inline.

Why:
- Useful for sanity checks on ingestion quality and prioritizing suspicious rows.
- Keeps prototype self-contained without building a full factor service.

Ignored for prototype:
- Jurisdiction/year/versioned factor catalogs and factor provenance workflows.

PM question I would ask:
- Should factors be centrally managed by data governance with version locking per reporting cycle?

## 7) Suspicion heuristics
Decision: Rule-based flags for missing mappings, odd billing periods, conversion failures, and unusually large quantities.

Why:
- Deterministic and explainable for analyst review.
- Easy to demo and debug in prototype constraints.

Ignored for prototype:
- Statistical anomaly models trained on historical tenant baselines.

PM question I would ask:
- Which false-positive/false-negative tradeoff should the review queue optimize for?
