# SevaAgent

Checkpoint 0 (portal reconnaissance) and checkpoint 1 (foundation + discovery/eligibility slice). Read `portal_validation.md` first.

## Run
```bash
docker compose up -d db                       # PostgreSQL + pgvector
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
python -m pytest                              # 13 tests
python -m app.cli create-admin you@example.com 'a-long-password'
uvicorn app.main:app --reload                 # http://localhost:8000/docs
cd ../frontend && npm install && npm run dev  # http://localhost:3000
```

## What works
- Register/login (scrypt + JWT), profile, role checks (student/admin).
- Admin fetches an official page (https, gov.in/nic.in only, robots.txt honoured, rate-limited), stores a SHA-256 snapshot.
- Admin adds schemes tied to a snapshot, then drafts rules with an official `source_reference` per criterion and approves them.
- Deterministic eligibility engine (ELIGIBLE / INELIGIBLE / INSUFFICIENT_INFORMATION). No LLM. Unverified rules, rules from another academic year and missing data never produce ELIGIBLE.
- Deadlines show OPEN/CLOSED only when an admin marked them verified; otherwise "Deadline not verified". Data older than 7 days is flagged.
- SHA-256 hash-chained audit log with tamper detection (`GET /api/audit/verify`).

## What does not exist yet (deliberately)
- **No scheme catalogue parser.** It needs the real NSP DOM, which was not inspected (see `portal_validation.md` section 4). Until then, admins add schemes by hand from official pages. The repo ships **no real scheme rules**.
- No documents/OCR, application drafts, Playwright agent or LangGraph. `ENABLE_PORTAL_AUTOMATION` is false and nothing reads it yet.
- Admin UI. Admin endpoints are API-only (use `/docs`).
- Rate limiting, email verification, password reset, CSRF/cookie sessions (token is in sessionStorage for now).
