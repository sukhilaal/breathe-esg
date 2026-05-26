# Breathe ESG Tech Intern Prototype

Django REST + React prototype for ingesting SAP, utility electricity, and corporate travel data, normalizing into a common activity ledger, and supporting analyst review + audit lock workflow.

## Stack
- Backend: Django 6 + Django REST Framework
- Frontend: React (Vite)
- Database: SQLite (prototype)

## Repository structure
- `backend/` Django project config
- `core/` Domain models, ingestion services, API views, management commands
- `frontend/` React analyst dashboard
- `sample_data/` Realistic fabricated source files
- `MODEL.md`, `DECISIONS.md`, `TRADEOFFS.md`, `SOURCES.md` required assignment docs

## Quickstart

### 1) Backend
```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_reference_data
python manage.py load_demo_data
python manage.py runserver
```

Backend API base: `http://localhost:8000/api`

### 2) Frontend
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Frontend URL (default): `http://localhost:5173`

## Core API endpoints
- `POST /api/ingest/sap/` (multipart with `tenant_slug`, `file` CSV)
- `POST /api/ingest/utility/` (multipart with `tenant_slug`, `file` CSV)
- `POST /api/ingest/travel/` (multipart with `tenant_slug`, `file` JSON)
- `GET /api/dashboard/summary/?tenant_slug=acme-enterprise`
- `GET /api/activities/?tenant_slug=acme-enterprise`
- `POST /api/activities/{id}/action/` with `approve|reject|lock`
- `GET /api/activities/{id}/audit/`

## Sample tenant
Seed command creates:
- Tenant slug: `acme-enterprise`
- Plant mappings for sample SAP rows
- Airport lookup set for travel distance derivation

## Validation and quality checks included
- Unit normalization and conversion aliases
- Missing plant mapping flag
- Unusual utility billing-period length flag
- Travel distance derivation from airport codes
- Quantity outlier thresholds by activity type
- Audit immutability: locked rows cannot be edited or overwritten on re-ingest

## Tests
```bash
python manage.py test
```

## Deployment notes
A `render.yaml` is included to deploy API + static web on Render.
After deployment, set frontend `VITE_API_BASE` to the API service URL + `/api`.

## Deploy to Render
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/sukhilaal/breathe-esg)
