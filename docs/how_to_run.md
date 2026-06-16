# How to Run FixMate with the GUI

## Prerequisites

Make sure these are running first:

1. **Docker services** — `docker compose up -d` (Postgres, Redis, MinIO, Ollama)
2. **API server** — `uvicorn fixmate.api.main:app --reload` (serves on `http://localhost:8000`)

## Start the Web GUI

```powershell
cd web
npm install        # first time only
npm run dev        # starts Vite dev server on http://localhost:5173
```

Open http://localhost:5173 in your browser.

> **Port conflict on Windows?** If you get `EACCES ::1:5173`, run:
> `npm run dev -- --host 127.0.0.1 --port 8123`

## Dev Login (DEV_AUTH=true mode)

On first load, the app prompts for an **org UUID, user UUID, and role**. The easiest way to get these:

```powershell
python scripts/seed_demo.py
```

This seeds a demo tenant and prints the IDs. Paste them into the login prompt.

**Role routing:**
- `tech` → chat interface (ask questions, get grounded answers)
- `curator` → review queue, document upload, equipment management
- `admin` → everything above + user/role management

## Quick Summary

| What | Command |
|------|---------|
| Infrastructure | `docker compose up -d` |
| API | `uvicorn fixmate.api.main:app --reload` |
| Web GUI | `cd web && npm run dev` |
