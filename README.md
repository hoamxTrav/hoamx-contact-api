# HOAMX Contact API

FastAPI-based backend that receives contact form submissions from https://www.hoamx.com
and stores them in a PostgreSQL database (Cloud SQL for Postgres).

## Endpoints

- `GET /health` – health probe
- `POST /api/contact` – receives JSON payload:

```jsonc
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "association": "Maple Ridge Townhomes",
  "role": "board",
  "message": "Hi, I would like a demo."
}

```
