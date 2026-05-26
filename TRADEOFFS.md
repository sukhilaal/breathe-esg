# TRADEOFFS

## 1) Not built: direct SAP/utility/travel OAuth integrations
Why not:
- In four days, connector auth, token rotation, retries, and vendor-specific pagination would crowd out core data-model quality.
- CSV/JSON ingestion still exercises the realistic normalization and review hard parts.

Consequence:
- Prototype is operations-assisted instead of fully automated ingestion.

## 2) Not built: enterprise auth/RBAC and row-level entitlements
Why not:
- Assignment focus is ingestion normalization and analyst sign-off logic.
- Auth stack (SSO, SCIM, role inheritance) is substantial and orthogonal to core pipeline correctness.

Consequence:
- Prototype assumes trusted analyst usage and is not production-secure.

## 3) Not built: full emission factor governance service
Why not:
- Production-grade factor governance requires versioning by geography, year, methodology, and auditor traceability.
- I implemented a small embedded factor map only to enable pipeline validation and review prioritization.

Consequence:
- CO2e outputs are prototype estimates and should not be used for statutory reporting without a governed factor engine.
