# ClinTrial AI – Platform Backend (Node + PostgreSQL) + Assistant Proxy

This is the platform backend (users, cases, sessions, scoring, analytics, leaderboard) that integrates with the existing python assistant service from medspeakai.

## What this repo connects to the python service (`medspeakai/main.py`) exposes:

- `POST /{laptop_code}/{mode}/{session_id}`
- JSON body: `{ "question": string, "history_summary": string, "force_local": bool }`
- JSON response: `{ "answer": string, ... }`

This Node backend calls it via `POST /assistant/query` and `POST /sessions/:sessionId/chat`.

---

## Quick start (Windows / Mac)

### 1) start PostgreSQL + Redis (Docker)
```bash
cd clintrial-backend
copy .env.example .env   # (Windows PowerShell: Copy-Item .env.example .env)
docker compose up -d
```

### 2) install deps + set up database
```bash
npm install
npx prisma generate
npx prisma migrate dev --name init
node prisma/seed.js
```

Seed creates:
- Admin: `admin@local.test` / `admin1234`
- University: UKM
- A few Systems, Diseases, and Cases

### 3) run the backend!!!!
```bash
npm run dev
```
Health check:
- `GET http://127.0.0.1:3000/health`

---

## connect to the existing python assistant service

1) run the python service (from your existing project):
```bash
py start.py
```
That starts FastAPI on port **8000**.

2) ensure `.env` in this backend has:
```
ASSISTANT_BASE_URL="http://127.0.0.1:8000"
ASSISTANT_LAPTOP_CODE="STUDENT_LAPTOP_01"
ASSISTANT_MODE="chat"
```

Now these endpoints will work:
- `POST /assistant/query`
- `POST /sessions/:sessionId/chat`

---

## API overview (v1)

### Auth
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `POST /auth/password/forgot`
- `POST /auth/password/reset`

### Core data
- `GET /universities`
- `GET /systems`
- `GET /systems/:systemId/diseases`

### Case flow
- `POST /cases/select`  (starts a session and returns the case)
- `POST /sessions/:sessionId/chat` (stores messages + calls Python assistant)
- `POST /sessions/:sessionId/submit` (basic scoring v1 + updates progress)

### Analytics
- `GET /analytics/summary`

### Leaderboard
- `GET /leaderboard?type=global&minSessions=3&limit=20`
- `GET /leaderboard?type=university&universityId=...`

### Admin (seed admin user)
- `POST /admin/universities`
- `POST /admin/systems`
- `POST /admin/diseases`
- `POST /admin/cases`
- `GET /admin/users`

---

## notes (important)
- this is v1. The scoring engine is intentionally simple placeholders and is designed to be upgraded tauu.
- keep secrets out of git. rn the python repo includes an NVIDIA key in files; move to env vars before pushing public.

## Example curl flow

### 1) register
```bash
curl -X POST http://127.0.0.1:3000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"fullName":"Sev","email":"sev@example.com","password":"password123","universityCode":"UKM"}'
```

### 2) login
```bash
curl -X POST http://127.0.0.1:3000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sev@example.com","password":"password123"}'
```
copy the returned `accessToken`.

### 3) list systems
```bash
curl http://127.0.0.1:3000/systems \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 4) select a case (starts a session)
```bash
curl -X POST http://127.0.0.1:3000/cases/select \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"systemId":"<SYSTEM_UUID>","difficulty":"MEDIUM"}'
```

### 5) chat inside the session (calls the python assistant service)
```bash
curl -X POST http://127.0.0.1:3000/sessions/<SESSION_UUID>/chat \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hi doctor, what could this be?"}'
```
