# JeBo Studios Backend

FastAPI backend for JeBo Studios, prepared for Railway deployment.

## Endpoints

- `GET /health` – service health check
- `POST /api/v1/process` – accepts an image upload and performs conservative, non-generative image normalization while preserving the product pixels as much as possible

## Railway

Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Health check path:

```text
/health
```

## Local run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open `http://localhost:8000/health`.
