# AI Collaboration Log

## AI tech stack

| Tool | Model | Role |
|------|-------|------|
| ChatGPT | GPT-5.5 | Read the assignment, clarify requirements, plan architecture, and draft the prompts/instructions for implementation |
| Cursor | Composer 2.5 | Primary implementation — backend, frontend, Docker, README, and most of this log |
| Cursor | Opus 4.8 | Final verification — cross-checked the repo, README, and AI_LOG against assignment requirements |

**How they worked together:** I started in ChatGPT 5.5 to understand what the assignment actually wanted and how to structure the build (stack choice, phased plan, prompt strategy). I then took those instructions into Cursor Composer 2.5 for implementation. Before submitting, I used Cursor Opus 4.8 to review everything critically — does it run, does the docs match the code, does the AI_LOG tell the truth.

Composer handled most of the coding in one continuous Cursor thread so architectural decisions, implementation, and fixes shared the same context. ChatGPT and Opus were separate review/planning passes on top of that.

---

# Prompts

## Initial collaboration prompt

Used with **Cursor Composer 2.5** (wording originally shaped in ChatGPT 5.5). Before writing any code, I wanted the AI to behave like a reviewer instead of a code generator.

```text
You are my senior technical partner.

Your job is NOT to make me feel my ideas are correct.
Your job is to improve the quality of this project.

Whenever I propose an idea:
- Challenge it if there is a better alternative.
- Recommend simpler solutions whenever possible.
- Explain trade-offs objectively.
- Point out unnecessary complexity.
- Tell me when an implementation introduces avoidable risk.
- If multiple approaches are reasonable, compare them instead of picking one automatically.
- If you don't have enough information, ask clarifying questions before recommending an implementation.

Do not optimize for agreeing with me.
Optimize for helping me ship the best possible MVP within one day.
```

This ended up setting the tone for the entire project. Instead of immediately generating code, the conversation became much more about trade-offs and design decisions.

---

## Backend

```text
Implement /backend with FastAPI. POST/GET/DELETE for URLs. Background task
pings every 60 seconds. Store status code, response time (ms), timestamp.
Treat network errors (timeout, DNS, connection refused) as DOWN, not just
HTTP error codes. Include Dockerfile and a /health endpoint for Docker
healthchecks. PostgreSQL via SQLAlchemy.
```

---

## Frontend

```text
React + Vite dashboard. Table of URLs with UP/DOWN badge, response time,
last checked. Form to add URL, button to delete. Poll GET /urls every 10
seconds. Keep styling minimal but readable. Use VITE_API_URL for the API
base so it works in Docker.
```

---

## Docker

```text
Wire backend, frontend, and Postgres in docker-compose.yml. One command:
docker compose up --build. Backend must wait for the DB to be ready.
Document test steps: https://example.com (UP) and http://localhost:9999 (DOWN).
```

---

## Final review

Run with **Cursor Opus 4.8**. This prompt found the event loop issue described later in this document.

```text
Final review mode.

Treat this as a submitted take-home assignment.
Review the entire repository, README, AI_LOG, Docker setup, architecture,
and code quality.

Be extremely critical.

Identify every issue, rank it by severity, suggest the smallest fix, then give:
- Final score (/10)
- Interview recommendation
- Top 5 improvements before submission

Do not suggest features beyond the assignment scope.
```

It also pointed out:

- missing frontend `.dockerignore`
- duplicate insert race
- conflicting CORS configuration

---

## AI_LOG review

Run with **Cursor Opus 4.8**. Before finishing, I reviewed the documentation itself.

```text
Treat AI_LOG.md as evidence of my engineering process.
Compare it against the repository and our conversation.
Identify anything that doesn't match what actually happened, sounds
AI-written, or could make an interviewer skeptical. Rewrite only those
sections. The goal is to make it read like genuine documentation while
remaining completely truthful.
```

This caught a few places where the log described behavior that the code didn't actually implement. I corrected the documentation instead of changing the code to match the story.

---

# What AI didn't decide

These were decisions I intentionally made myself.

- Choosing FastAPI + PostgreSQL over simpler alternatives.
- Rejecting Redis, Celery, WebSockets, and APScheduler.
- Treating network failures as **DOWN** instead of only HTTP errors.
- Running an immediate health check after creating a URL.
- Reviewing generated SQLAlchemy code and updating 1.x query patterns.
- Deciding where the MVP boundary should be.
- Running every verification step manually instead of trusting generated output.
- Correcting the AI log when it overstated something.

---

# Scheduler placement

This was probably the biggest architectural decision.

I considered three approaches.

| Option | Pros | Cons |
|---------|------|------|
| asyncio loop | No extra infrastructure | Dies with the process |
| APScheduler | Nice scheduling API | Extra dependency |
| Celery + Redis | Production-ready queue | Far too much infrastructure |

Cursor suggested using an asyncio background task inside the FastAPI lifespan.

After checking the assignment requirements again, I agreed.

The assignment only monitors a few dozen URLs every minute. Redis and Celery would have introduced more containers, more moving parts, and more failure modes without solving a real problem.

The final design uses:

- in-process asyncio loop
- 60 second interval
- configurable through `CHECK_INTERVAL_SECONDS`

The important part wasn't the timer—it was making sure the actual HTTP requests never blocked the event loop.

---

# Polling vs WebSockets

I looked at polling, WebSockets, and SSE.

Honestly, this decision only took a few minutes.

Checks only happen every 60 seconds, so pushing updates instantly doesn't really improve anything.

Polling every 10 seconds with `GET /urls` kept the frontend simple and avoided extra connection management.

---

# SQLite or PostgreSQL?

Either would have worked.

I picked PostgreSQL because Docker Compose already needed a database service, and it's much closer to how I'd actually deploy the application.

Using `postgres:16-alpine` also made the deployment sketch more realistic.

---

# What counts as UP?

One thing I wanted to get right was handling unreachable hosts.

The assignment specifically asks for testing with an invalid URL, so DNS failures, connection timeouts, and refused connections all needed to become **DOWN**.

The generated code already handled that correctly.

One mistake was actually mine.

An earlier version of this document claimed the threshold was **2xx only**.

After checking the implementation, I realized the code actually treats **any status below 500** as UP.

Instead of changing the code, I corrected the documentation.

Current behavior:

- Status code < 500 → UP
- `httpx.RequestError` → DOWN
- HTTP 5xx → DOWN

Known limitation:

A site returning 404 is still considered UP because the server is reachable. I left that behavior unchanged because the assignment doesn't require stricter semantics.

---

# Things I said no to

## Redis + Celery

Too much infrastructure for the assignment.

Extra containers, extra worker processes, serialization, and a more complicated Compose setup without solving a real problem.

---

## WebSockets

Polling every 10 seconds already matched the monitoring frequency.

Adding persistent connections would have increased complexity for very little benefit.

---

## APScheduler

Only one recurring task exists.

A simple asyncio loop was easier to understand and required fewer dependencies.

---

## Waiting 60 seconds after creating a URL

I didn't like the idea of showing **PENDING** for up to a minute.

The application performs one immediate health check after creation, then the scheduler takes over.

---

# Bugs

## Synchronous HTTP calls blocking the event loop

This turned out to be the most important issue in the project.

The scheduler itself was asynchronous.

The HTTP requests inside it were not.

That meant every slow request blocked the same event loop serving API traffic.

Everything looked correct:

- `async def`
- `create_task()`
- `await`

The bug only appeared when a URL actually timed out.

The fix was moving the HTTP calls into worker threads using:

- `asyncio.to_thread()`
- `asyncio.gather()`

After the change, I repeated the test using a URL that intentionally timed out for the full 10 seconds while polling `/health` once every second.

The API stayed responsive throughout the scheduler cycle.

The same change also meant URL checks could run concurrently instead of one after another.

---

## PostgreSQL startup ordering

I expected to find this issue.

I didn't.

The generated project already included:

- database retry loop
- PostgreSQL healthcheck
- `service_healthy` dependency

I still verified it manually using a clean startup from empty Docker volumes.

---

## Smaller fixes

- Updated SQLAlchemy 1.x query patterns to SQLAlchemy 2.x.
- Fixed frontend handling of FastAPI validation errors where `detail` can be a list instead of a string.

---

# Other small decisions

- FastAPI for async support and request validation.
- `httpx` with a 10 second timeout.
- Nginx serving the Vite build.
- Single backend instance for MVP scope.

---

# Verification

Performed using:

```bash
docker compose down -v
docker compose up --build
```

Verified:

- Backend starts.
- Frontend loads.
- PostgreSQL initializes correctly.
- `https://example.com` reports **UP**.
- `http://localhost:9999` reports **DOWN**.
- Duplicate POST returns **409**.
- Scheduler updates timestamps every cycle.
- API remains responsive during slow requests.
- DELETE removes URLs and history.
- Frontend production build succeeds.

One earlier failure turned out to be because Docker Desktop wasn't running, not because of the application itself.

---

# Reflection

Looking back, AI was much more valuable during review than during generation.

Generating CRUD code was the easy part.

The useful conversations were about trade-offs, removing unnecessary complexity, reviewing generated code, and verifying edge cases.

The biggest risk wasn't bad generated code.

It was code that looked reasonable enough that I might have accepted it without reading it carefully.

The event loop issue was a good reminder of that.

I intentionally kept the final solution simple because the assignment rewarded execution and engineering judgment over additional infrastructure.
