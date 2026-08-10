# Repo Assistant

A Python backend service that ingests a GitHub repository's full issue and pull request history and makes it queryable. The premise is that the *why* behind a codebase — why a decision was made, why an approach was rejected — is buried in closed issues and PR threads nobody reads. This surfaces it.

**Current state:** ingestion runs asynchronously through a Redis-backed job queue. Retrieval and question answering are next.

---

## Architecture

Three processes that share nothing but Redis:

```
   POST /ingest                        rq worker
   ┌──────────┐   enqueue   ┌───────┐   claim    ┌────────┐
   │ FastAPI  │ ──────────► │ Redis │ ─────────► │ worker │ ──► GitHub API
   │   API    │             │       │            │        │ ──► data/*.json
   └──────────┘ ◄────────── └───────┘ ◄───────── └────────┘
   GET /jobs/{id}   read status/result   write status/result
```

The API never touches GitHub. It writes a job — a function reference plus arguments — into Redis and returns a ticket. The worker, a separate process, claims it and does the ~114 seconds of crawling. Job state lives in Redis because that's the only thing both processes can see.

---

## Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1          # PowerShell; use source .venv/bin/activate on Unix
pip install -r requirements.txt
```

Create a `.env` file with a GitHub personal access token (classic, `public_repo` scope):

```
GITHUB_TOKEN=ghp_xxxxx
```

Bring up all three services:

```bash
docker compose up --build
```

That starts Redis, the API on port 8000, and a worker — the API and worker run the same image with different commands.

Interactive docs at http://localhost:8000/docs.

<details>
<summary>Running without containers</summary>

```bash
pip install -r requirements-dev.txt
docker compose up -d redis
uvicorn app.main:app --reload
rq worker ingest --url redis://localhost:6379/0 --worker-class rq.SimpleWorker
```

`--worker-class rq.SimpleWorker` is only needed on Windows: RQ's default worker forks a child per job and `os.fork()` doesn't exist there. In the container the worker runs on Linux, so the default forking worker is used — which also means a crashed job can't take the worker down with it.

</details>

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Eleven tests, no live Redis or network needed — GitHub is mocked with `respx` and the queue is stubbed. They cover the pagination loop's termination (including the exact-multiple-of-100 edge case), the rate-limit retry and when it gives up, request validation, and that `POST /ingest` enqueues rather than crawling.

CI runs them on every push, then builds the Docker image.

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check. |
| `POST` | `/ingest` | Enqueues a crawl. Returns `202` with a job ID immediately. |
| `GET` | `/jobs/{id}` | Job status: `queued` / `started` / `finished` / `failed`. |

```bash
curl -X POST localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"repo":"fastapi/fastapi"}'
# {"repo":"fastapi/fastapi","job_id":"c12d3fbf-..."}

curl localhost:8000/jobs/c12d3fbf-...
# {"status":"finished","result":{"owner":"fastapi","repo":"fastapi","records_count":9708}}
```

Repos are validated as `owner/repo` by Pydantic before the handler runs.

Two behaviours worth knowing rather than discovering:

- **A nonexistent repo still returns 202.** The API can't know at response time — it never contacts GitHub. The failure surfaces through `/jobs/{id}` as `failed`. That's the cost of going asynchronous, not a bug.
- **Finished jobs disappear after 500 seconds.** RQ's `result_ttl` expires them, so polling an old job ID returns 404 even though it succeeded.

---

## Measurements

Same repo, same machine, before and after moving ingestion off the request path.

| `POST /ingest` response | |
|---|---|
| Synchronous (Aug 6) | **113,700 ms** |
| Queued (Aug 8) | **3.3 – 5.9 ms** |

The first request after a restart costs ~2.1 s for lazy imports and Redis pool setup; the figures above are steady-state.

The crawl itself still takes ~114 seconds — the queue did not make it faster, it moved it off the request path. What changed is that the client is no longer holding a connection open while it happens.

### The crawl itself

| | `fastapi/fastapi` | `pallets/flask` |
|---|---|---|
| Records ingested | 9,708 | 5,599 |
| Pages (`per_page=100`) | 98 | 56 |
| Wall time | 113.7 s | 63.5 s |
| Time per page | 1.16 s | 1.13 s |
| Stored JSON | 58.6 MB | 30.6 MB |

Per-page cost is effectively constant across two unrelated repos, so ingest time scales with page count rather than payload size. The work is I/O-bound — the process spends nearly all of those 113 seconds blocked on the network — which is why the fix was to move it off the request path rather than to optimise the parsing.

---

## Design notes

**Issues and PRs are stored together.** GitHub's data model treats every pull request as an issue, so `/repos/{owner}/{repo}/issues` returns both, distinguished by a `pull_request` key. There's no server-side filter for this; the Search API supports `type:issue` but caps at 1,000 results, and the GraphQL API models them separately but was out of scope. Both kinds are kept, since PR threads carry as much of the reasoning as issues do.

**Raw payloads are stored, not extracted fields.** Field selection happens at read time, so changing the field set later doesn't require re-crawling 98 pages. The cost is disk: nested `user`, `labels`, and `reactions` objects are why one repo lands at 58 MB.

**Pagination counts pages rather than following the `Link` header.** Simpler, with no string parsing. The tradeoff is that requests must run sequentially, since a page's existence isn't known until the previous one returns short — `Link`'s `rel="last"` would allow the crawl to be parallelised.

---

## Next

- Dockerfiles for API and worker, all three services under one `docker compose up`
- Tests and CI
- Chunking, embeddings, and an `/ask` endpoint
