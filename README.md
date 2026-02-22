# Booklify

Booklify is an end-to-end AI bookkeeping and financial assistant platform for freelancers and small businesses.
It automates accounting workflows from document ingestion through categorization, reporting, alerts, and chatbot-assisted operations.

## Core capabilities

- Full bookkeeping automation for:
  - Transactions (income, expenses, receivables, payables, payroll, marketing, tax)
  - Categorization with confidence scoring and review flags
  - Tax-aware summaries and country profile defaults
- Country-aware logic for **AU, US, UK, IN, FR, CUSTOM**
- Language-aware responses in **English** and **French**
- Document ingestion for:
  - CSV, XLSX, PDF, TXT, JPG, PNG (heuristic extraction for non-tabular files)
  - Duplicate detection via SHA-256
  - Corrupt/empty file rejection
  - Queue-backed processing mode (inline/threadpool)
- Accountant-ready exports:
  - CSV single sheet
  - XLSX multi-sheet (All Transactions, Income, Expenses, Receivables, Payables)
- Notifications and reminders:
  - Unusual transaction alerts
  - High upload volume
  - Low-confidence review flags
  - Tax liability and deadline reminders
  - Unpaid receivable reminders
- Financial snapshot and advisory:
  - Net profit, income/expense totals, cash in/out, receivables/payables
  - Friendly advisory language (non-jargon)
- Internal chatbot:
  - Add, modify, delete transactions
  - Fetch summaries and alerts
  - Store lightweight user preferences
- Versioning/rollback support for documents:
  - Version increments for same filename uploads
  - Restore a previous version's transactions into current version

## Tech stack

- FastAPI
- SQLAlchemy + SQLite
- OpenPyXL + CSV engine
- PyPDF extraction
- Pydantic v2

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn booklify.main:app --reload
```

API base URL: `http://127.0.0.1:8000/api/v1`

## Quick API walkthrough

1. Create a business profile:

```http
POST /api/v1/businesses
```

2. Upload one or many documents:

```http
POST /api/v1/businesses/{business_id}/documents/upload
```

3. Review transactions:

```http
GET /api/v1/businesses/{business_id}/transactions
```

4. Correct categories to improve future auto-categorization:

```http
POST /api/v1/transactions/{tx_id}/corrections
```

5. Export accountant-ready data:

```http
GET /api/v1/businesses/{business_id}/exports?export_format=csv
GET /api/v1/businesses/{business_id}/exports?export_format=xlsx
```

6. Chat with assistant:

```http
POST /api/v1/businesses/{business_id}/chat
```

## Testing

```bash
pytest -q
```
