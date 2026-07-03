# Uptime Monitor

A lightweight full-stack uptime monitor: register URLs, ping them every ~60 seconds, and view UP/DOWN status with latest response time on a simple dashboard.

**Stack:** FastAPI · PostgreSQL · React · Docker Compose

## One-line setup

```bash
docker compose up --build
```

**Prerequisites:** Docker Desktop (or Docker Engine + Compose v2) running.

First build may take a few minutes. When all services are healthy:

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Health check | http://localhost:8000/health |

Stop everything:

```bash
docker compose down
```

Wipe data and start fresh:

```bash
docker compose down -v
docker compose up --build
```

## Architecture

```text
Browser (React dashboard)
        |
        |  HTTP polling every 10s
        v
   FastAPI backend
        |
        +--> REST API (register / list / delete URLs)
        |
        +--> In-process scheduler (ping every 60s)
        |
        v
   PostgreSQL
        |
        +--> monitored_urls
        +--> health_checks (status code, response time, timestamp)
```

| Layer | Tech | Role |
|-------|------|------|
| Frontend | React + Vite + nginx | Dashboard, add/delete URLs, auto-refresh |
| Backend | FastAPI + SQLAlchemy | API + health-check scheduler |
| Database | PostgreSQL 16 | URL registry + check history |
| Orchestration | Docker Compose | One-command local startup |

Each health check stores: HTTP status code (or error), response time (ms), UP/DOWN flag, and timestamp.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `GET` | `/urls` | List monitored URLs with latest check |
| `POST` | `/urls` | Add URL (`{"url": "https://example.com"}`) — runs an immediate check |
| `DELETE` | `/urls/{id}` | Remove a URL and its history |
| `GET` | `/urls/{id}/history` | Last 20 checks for a URL (API only; UI shows latest) |

Scheduler interval defaults to 60 seconds (`CHECK_INTERVAL_SECONDS` in `docker-compose.yml`).

## Testing steps

These are the exact steps reviewers can follow locally.

1. Run `docker compose up --build`.
2. Open http://localhost:3000.
3. **Healthy URL**
   - Enter `https://example.com`
   - Click **Monitor URL**
   - Expected: **UP**, response time in ms, recent "Last checked" time
4. **Broken URL**
   - Enter `http://localhost:9999`
   - Click **Monitor URL**
   - Expected: **DOWN** (connection refused from the backend container)
5. Wait up to 60 seconds — the dashboard auto-refreshes every 10s and scheduler timestamps should update without a manual reload.

### API smoke test

```bash
# Healthy URL
curl -s -X POST http://localhost:8000/urls \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}' | python3 -m json.tool

# Broken URL
curl -s -X POST http://localhost:8000/urls \
  -H "Content-Type: application/json" \
  -d '{"url":"http://localhost:9999"}' | python3 -m json.tool

# List all with latest status
curl -s http://localhost:8000/urls | python3 -m json.tool
```

### Clean clone verification

```bash
git clone <your-repo-url>
cd <repo-name>
docker compose down -v
docker compose up --build
```

Then repeat the testing steps above. Replace `<your-repo-url>` and `<repo-name>` after publishing to GitHub.

## Design trade-offs

| Decision | Why |
|----------|-----|
| PostgreSQL | Production-like persistence; fits multi-container Compose |
| In-process scheduler | ~50 URL checks/minute total doesn't need a job queue |
| HTTP polling (10s) | Simpler than WebSockets; backend checks run every 60s |
| FastAPI | Async-friendly, fast to build, clear request validation |
| Single backend process | Intentional MVP scope |

Rejected alternatives (Redis, Celery, WebSockets, APScheduler) and the reasoning are in [`AI_LOG.md`](AI_LOG.md).

## Known limitations

Intentional MVP scope — not production monitoring.

- Single backend instance; scheduler runs in-process
- No authentication
- UP/DOWN uses HTTP status `< 500`; reachable 4xx responses count as UP
- No alerting or retry/backoff beyond the next 60s cycle
- Adding a URL runs an immediate inline ping — a slow/dead URL can take up to the 10s timeout before the POST responds
- UI shows latest check only (`/history` API exists but is not visualized)
- Optimized for dozens of URLs, not thousands

## Deployment sketch

```text
Internet
   |
Load Balancer
   |
   +--> Frontend (static React build)
   |
   +--> Backend (FastAPI + in-process scheduler)
   |
   +--> Managed PostgreSQL
```

Hypothetical Terraform-style outline:

```hcl
resource "aws_ecs_service" "backend" {
  name            = "uptime-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 1
}

resource "aws_ecs_service" "frontend" {
  name            = "uptime-frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = 1
}

resource "aws_db_instance" "postgres" {
  engine            = "postgres"
  instance_class    = "db.t4g.micro"
  allocated_storage = 20
}
```

One backend task runs both the API and scheduler. Horizontal scale would need a dedicated check worker — out of scope here.

## Project structure

```text
/backend          FastAPI API + scheduler
/frontend         React dashboard
docker-compose.yml
README.md
AI_LOG.md         AI collaboration log (assignment deliverable)
```
