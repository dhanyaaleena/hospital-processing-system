# Hospital Bulk Processing System

A bulk CSV upload and processing system that integrates with the [Hospital Directory API](https://hospital-directory.onrender.com/docs) to create and activate hospital records in batch.

---

## Overview

The Hospital Directory API handles individual hospital records. This system sits on top of it to support bulk operations — upload a CSV, and the system creates each hospital via the API, then activates the entire batch in one shot.

---

## Tech Stack

- **Language:** Python 3.8+
- **Framework:** FastAPI
- **HTTP Client:** httpx (async)
- **Storage:** In-memory (no database required)
- **WebSocket:** Built-in FastAPI WebSocket support
- **Frontend:** Vanilla HTML/CSS/JS (served by FastAPI)

---

## Getting Started

### Local Setup

```bash
# Clone the repo
git clone <your-repo-url>
cd hospital-processing-system

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload
```

Open **http://localhost:8000** in your browser.

### Docker

```bash
docker compose up
```

---

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed:

```env
HOSPITAL_API_BASE_URL=https://hospital-directory.onrender.com
MAX_CSV_HOSPITALS=20
REQUEST_TIMEOUT=30.0
```

---

## CSV Format

| Column    | Required | Description              |
|-----------|----------|--------------------------|
| `name`    | Yes      | Hospital name            |
| `address` | Yes      | Full address             |
| `phone`   | No       | Contact phone number     |

**Rules:**
- Maximum **20 hospitals** per CSV
- UTF-8 encoding (BOM-safe — Excel exports work)
- Headers must be on the first row

**Example:**

```csv
name,address,phone
General Hospital,123 Main Street,555-1000
City Medical Center,456 Oak Avenue,555-2000
Riverside Clinic,789 River Road,
```

Sample files included: `sample.csv`, `sample_batch_1.csv`, `sample_batch_2.csv`, `sample_with_failures.csv`

---

## API Endpoints

### Bulk Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/hospitals/bulk` | Upload CSV and start batch processing |
| `GET` | `/hospitals/bulk` | List all batches (newest first) |
| `GET` | `/hospitals/bulk/{batch_id}/status` | Get full status and results for a batch |
| `POST` | `/hospitals/bulk/{batch_id}/resume` | Retry only the failed hospitals in a batch |
| `WS` | `/hospitals/bulk/{batch_id}/ws` | Real-time progress via WebSocket |

### Utility

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/` | Web UI |

---

## Processing Workflow

1. **Upload** — Client sends a multipart `POST /hospitals/bulk` with a CSV file
2. **Validate** — Server parses and validates the CSV (required fields, row limit, encoding)
3. **Batch ID** — A UUID is generated for this batch
4. **Create** — All hospitals are created concurrently via `POST /hospitals/` on the Hospital Directory API, each tagged with the batch ID
5. **Activate** — Once all hospitals are created, `PATCH /hospitals/batch/{batch_id}/activate` is called to make them all active
6. **Return** — The API returns `202 Accepted` immediately; progress is tracked via WebSocket or polling

### Response Example

```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_hospitals": 10,
  "processed_hospitals": 9,
  "failed_hospitals": 1,
  "processing_time_seconds": 5.2,
  "batch_activated": true,
  "hospitals": [
    {
      "row": 1,
      "hospital_id": 101,
      "name": "General Hospital",
      "status": "created_and_activated"
    },
    {
      "row": 3,
      "hospital_id": null,
      "name": "Broken Clinic",
      "status": "failed",
      "error": "500 Internal Server Error"
    }
  ]
}
```

### Batch Statuses

| Status | Meaning |
|--------|---------|
| `pending` | Queued, not started yet |
| `processing` | Currently creating hospitals |
| `completed` | All hospitals created and activated |
| `partial` | Some succeeded, some failed |
| `failed` | All hospitals failed |

---

## Resume Capability

If a batch ends in `partial` or `failed` status, you can retry the failed hospitals without reprocessing the ones that already succeeded:

```bash
POST /hospitals/bulk/{batch_id}/resume
```

Only hospitals with `status: failed` are retried. Already-created hospitals are skipped.

---

## Real-Time Progress

### WebSocket

Connect to `/hospitals/bulk/{batch_id}/ws` to receive live events:

```json
{ "event": "started", "batch_id": "..." }
{ "event": "progress", "row": 3, "processed": 3, "failed": 0, "total": 10, "hospital_status": "created" }
{ "event": "completed", "status": "completed", "batch_activated": true, "processed": 10, "failed": 0 }
```

### Polling

```bash
GET /hospitals/bulk/{batch_id}/status
```

Poll this endpoint to check progress at your own pace.

---

## Web UI

Open **http://localhost:8000** for a browser-based testing interface.

**New Batch tab:**
- Drag & drop or click "Choose CSV file" to upload — processing starts immediately
- Step indicator shows: Validating CSV → Submitting batch → Processing hospitals
- Live event stream shows each hospital as it's created
- Results table with per-hospital status after completion
- "Resume failed hospitals" button appears when there are failures

**Batch History tab:**
- Lists all batches processed in the current session
- Click "Details" on any batch to see the full per-hospital breakdown
- Refresh and Resume buttons per batch

---

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

**Test coverage:**
- CSV parsing: valid files, missing columns, missing values, BOM encoding, row limits
- Endpoints: bulk create, status polling, validation, resume, error scenarios, API failure simulation

---

## Bonus Features Implemented

| Feature | Details |
|---------|---------|
| Real-time progress | WebSocket stream per batch |
| Polling endpoint | `GET /hospitals/bulk/{batch_id}/status` |
| Resume failed batches | `POST /hospitals/bulk/{batch_id}/resume` |
| Concurrent processing | All hospitals created in parallel via `asyncio.gather` |
| Batch history | `GET /hospitals/bulk` lists all processed batches |
| Web UI | Single-page interface with live progress |
| Docker | `Dockerfile` + `docker-compose.yml` included |
| Tests | Unit + integration tests with mocked API |

---


**Start command:**
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set the `HOSPITAL_API_BASE_URL` environment variable to the Hospital Directory API base URL in your Render service settings.
