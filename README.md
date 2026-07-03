# Uptime Monitor

A lightweight full-stack uptime monitor that periodically pings registered URLs and displays whether each one is up or down, along with response time.

## One-line setup

```bash
docker compose up --build
```

Then open:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Health check: http://localhost:8000/health

## Architecture

```text
Browser (React dashboard)
        |
        |  HTTP polling every 10s
        v
   FastAPI backend
        |
        +--> REST API (register/list/delete URLs)
        |
        +--> In-process scheduler (ping every 60s)
        |
        v
   PostgreSQL
        |
        +--> monitored_urls
        +--> health_checks (status, response time, timestamp)
```

**Components**

| Layer | Tech | Role |
|-------|------|------|
| Frontend | React + Vite + nginx | Dashboard, add/delete URLs, auto-refresh |
| Backend | FastAPI + SQLAlchemy | API + health-check scheduler |
| Database | PostgreSQL 16 | URL registry + check history |
| Orchestration | Docker Compose | One-command local startup |

## Design trade-offs

| Decision | Why |
|----------|-----|
| PostgreSQL | Production-like persistence; fits multi-container Compose |
| In-process scheduler | Assignment scale (~50 URL checks/minute total) doesn't need a job queue |
| HTTP polling | Simpler than WebSockets; checks already run every 60s |
| FastAPI | Rapid development, async support, clear API validation |
| Single backend process | Intentional MVP scope; easy to run and review |

See `AI_LOG.md` for rejected alternatives (Redis, Celery, WebSockets) and reasoning.

## Testing steps

1. Start the stack with `docker compose up --build`.
2. Open http://localhost:3000 in your browser.
3. Add a healthy URL:
   - Enter `https://example.com`
   - Click **Monitor URL**
   - Expected: status shows **UP** with a response time in milliseconds
4. Add a broken URL:
   - Enter `http://localhost:9999`
   - Click **Monitor URL**
   - Expected: status shows **DOWN** (connection refused)
5. Wait up to 60 seconds and confirm the dashboard auto-refreshes with updated check timestamps.

### Clean clone verification

```bash
git clone <your-repo-url>
cd <repo>
docker compose down -v
docker compose up --build
```

Then repeat the testing steps above.

### API smoke test

```bash
curl -X POST http://localhost:8000/urls \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'

curl http://localhost:8000/urls
```

## Known limitations

This is an intentional MVP—not production monitoring.

- Single backend instance; scheduler is in-process
- No authentication or multi-tenant isolation
- UP/DOWN is based on HTTP status < 500; reachable 4xx responses count as UP
- No retry/backoff strategy beyond the next 60s cycle
- No alerting (email/Slack/PagerDuty)
- Adding a URL runs an immediate check inline, so registering a slow, unreachable URL can take up to the 10s ping timeout to respond
- No historical charts—latest check per URL only (history API exists but UI doesn't visualize it)
- Optimized for dozens of URLs, not thousands
- Frontend polls; no WebSocket push

These are scope choices, not oversights. See `AI_LOG.md` for the decision process.

## Deployment sketch

For a small MVP, a simple cloud topology would be:

```text
Internet
   |
Load Balancer
   |
   +--> Frontend container (static React build)
   |
   +--> Backend container (FastAPI + scheduler)
   |
   +--> Managed PostgreSQL
```

Example Terraform-style outline:

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

One backend task runs both the API and the in-process scheduler. Scale-out would require moving checks to a dedicated worker—out of scope for this assignment.

## Project structure

```text
/backend     FastAPI API + health-check scheduler
/frontend    React dashboard
docker-compose.yml
README.md
AI_LOG.md
```
