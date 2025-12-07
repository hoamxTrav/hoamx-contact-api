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

and then maybe the “Environment variables” section we drafted earlier.

---

### TL;DR

- Backend code: ✅ looks good
- Workflow: ✅ structurally correct, just needs real `PROJECT_ID` + secrets
- Add: `Procfile` for a clean Cloud Run start command

If you want, next we can do the Firebase side: I can write your `firebase.json` `rewrites` block exactly so `/api/contact` → this Cloud Run service and your `contact.html` form just calls `fetch("/api/contact", …)`.
