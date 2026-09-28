# HDAOS — Health Dispensary Analytical Ordering System

![CI](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/ci.yml/badge.svg)

HDAOS is a full-stack pharmacy operations platform: AI-assisted supplier document
ingest, FEFO batch/inventory management, procurement automation, and a built-in CRM —
built with **Django 6 + DRF + Celery** on the backend and **React 19 + Vite +
TypeScript** on the frontend.

## Features

- **AI Document Ingest** — upload supplier invoices, delivery notes, or client
  receipts (PDF/JPG/PNG); an LLM extracts structured line items, which you can
  review and edit before committing. Commits go through an approval workflow, and
  accepted invoices automatically create stock lots and recompute stock-on-hand.
  High-value invoices are flagged for extra scrutiny.
- **Inventory & Lots** — batch tracking with expiry tiers, automatic expiry scans
  that lock expired lots, and FEFO (First-Expired-First-Out) dispense suggestions.
- **Procurement** — reorder-point-driven procurement suggestions and per-supplier
  purchase-order creation with a submit/approve lifecycle.
- **CRM** — accounts, contacts (patients/prescribers/buyers), leads, opportunities,
  pipeline stages, campaigns, tasks, activities, and refill reminders.
- **Approvals & RBAC** — every sensitive action (user activation, high-value
  commits, unlocks) flows through an approval queue; role-based permissions for
  ADMIN, PHARMACIST, LOGISTICS, PROCUREMENT, SALES, and VIEWER.
- **Notifications & Audit** — in-app notification center and a full audit trail,
  including per-document AI ingest audits with provider/model tracking.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6, Django REST Framework, Celery + Redis, SimpleJWT |
| Database | PostgreSQL (prod) / SQLite (dev & tests) |
| Frontend | React 19, Vite 6, TypeScript, Tailwind CSS 4, Recharts |
| AI | Multi-provider LLM support (Gemini, Claude, OpenAI, DeepSeek, OpenRouter) |
| Testing | pytest + pytest-django (backend), Vitest + Testing Library (frontend) |
| CI | GitHub Actions — runs both test suites and the production build on every push |

## Project Structure

```
health-dispensary-analytical-ordering-system/
├── apps/               # Django apps (accounts, catalog, lots, orders, ingest,
│                       #   llm, approvals, crm, notifications, audit, intelligence)
├── hdaos/              # Django project (settings, celery, urls)
├── frontend/           # React SPA (Vite)
├── management/         # Django management commands
├── seed_synthetic.py   # Idempotent demo-data seeder (SYN-* namespace)
├── simulate_usage.py   # End-to-end API usage simulation (52 checks)
├── simulate_round2.py  # Second-round edge-case simulation (54 checks)
├── docker-compose.yml  # Postgres + Redis + web + worker + beat
└── .github/workflows/  # CI (pytest + vitest + vite build)
```

## Quick Start (Local Development)

### Backend

```bash
cd health-dispensary-analytical-ordering-system

python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt

cp .env.example .env        # then edit values as needed

python manage.py migrate
python seed_synthetic.py    # optional: loads demo data (see credentials below)

python manage.py runserver 127.0.0.1:8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev                 # http://localhost:5173 (proxies /api to :8000)
```

### Demo Credentials

After running `python seed_synthetic.py`:

| Username | Role | Password |
|---|---|---|
| `devadmin` | ADMIN (full access) | `e2e-pass-1234` |
| `synpharm` | PHARMACIST | `e2e-pass-1234` |
| `synsales` | SALES | `e2e-pass-1234` |
| `synproc`  | PROCUREMENT | `e2e-pass-1234` |

> Demo/dev credentials only — never use them anywhere real.

## Testing

```bash
# Backend — 442 tests
python -m pytest

# Frontend — 42 tests + typecheck + production build
cd frontend
npm run test
npm run build
```

CI (`.github/workflows/ci.yml`) runs both suites plus the production build on
every push and PR to `main`.

## Simulation Tooling

The repo ships with the scripts used to validate the system end-to-end:

- `seed_synthetic.py` — creates/updates a realistic synthetic dataset
  (products, lots with tiered expiries, CRM records, invoices). All rows are
  namespaced `SYN-` for idempotency; `--wipe` removes them first.
- `simulate_usage.py` — drives the real API like a user and reports pass/fail
  checks (52 checks).
- `simulate_round2.py` — adversarial/edge-case pass (54 checks).
- `run_scans.py` — triggers the expiry-scan maintenance tasks.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

This starts Postgres 15, Redis 7, the Django/gunicorn web tier on `:8000`, and
Celery worker + beat containers.

## Configuration

Copy `.env.example` to `.env` and fill in:

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret (change in production) |
| `DATABASE_URL` | PostgreSQL connection (SQLite used by default in dev/tests) |
| `REDIS_URL` | Celery broker / result backend |
| `FERNET_KEY` | Encryption key for sensitive fields (required when `DEBUG=False`) |
| `GEMINI_API_KEY` / `CLAUDE_API_KEY` / `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` | LLM providers for AI ingest |
| `EMAIL_HOST` / `EMAIL_PORT` | Outbound email |
| `CORS_ALLOWED_ORIGINS` | Frontend origins allowed to call the API |

## Notes

- The development server binds SQLite (`dev.db`) by default; production
  deployments should use the provided PostgreSQL/Redis compose stack.
- Add a `LICENSE` before publishing if you intend to open-source this code.
