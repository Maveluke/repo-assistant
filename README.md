# Repo Assistant

A Python backend service that ingests a GitHub repository's full issue and pull request history and makes it queryable. The premise is that the *why* behind a codebase — why a decision was made, why an approach was rejected — is buried in closed issues and PR threads nobody reads. This surfaces it.

**Current state:** ingestion works end to end. Retrieval and question answering are next.

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

Run the API:

```bash
uvicorn app.main:app --reload
```

Interactive docs at http://localhost:8000/docs.

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check. |
| `POST` | `/ingest` | Fetches every issue and PR for a repo and writes them to `data/{owner}-{repo}.json`. |

```bash
curl -X POST localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"repo":"fastapi/fastapi"}'
```

Repos are validated as `owner/repo` by Pydantic before the handler runs. A missing repo returns 404, an unreachable GitHub returns 504, and auth or rate-limit failures return 502.

---

## Measurements

Ingestion is synchronous today, so `POST /ingest` blocks for the full crawl.

| | `fastapi/fastapi` | `pallets/flask` |
|---|---|---|
| Records ingested | 9,708 | 5,599 |
| Pages (`per_page=100`) | 98 | 56 |
| Wall time | **113.7 s** | **63.5 s** |
| Time per page | 1.16 s | 1.13 s |
| Stored JSON | 58.6 MB | 30.6 MB |

Per-page cost is effectively constant across two unrelated repos, so ingest time scales with page count rather than payload size. The work is I/O-bound — the process spends nearly all of those 113 seconds blocked on the network — which is why the fix is to move it off the request path rather than to optimise the parsing.

---

## Design notes

**Issues and PRs are stored together.** GitHub's data model treats every pull request as an issue, so `/repos/{owner}/{repo}/issues` returns both, distinguished by a `pull_request` key. There's no server-side filter for this; the Search API supports `type:issue` but caps at 1,000 results, and the GraphQL API models them separately but was out of scope. Both kinds are kept, since PR threads carry as much of the reasoning as issues do.

**Raw payloads are stored, not extracted fields.** Field selection happens at read time, so changing the field set later doesn't require re-crawling 98 pages. The cost is disk: nested `user`, `labels`, and `reactions` objects are why one repo lands at 58 MB.

**Pagination counts pages rather than following the `Link` header.** Simpler, with no string parsing. The tradeoff is that requests must run sequentially, since a page's existence isn't known until the previous one returns short — `Link`'s `rel="last"` would allow the crawl to be parallelised.

---

## Next

- Move ingestion to a Redis-backed job queue so `/ingest` returns immediately
- `GET /jobs/{id}` for status polling
- Chunking, embeddings, and a `/ask` endpoint
- Tests, Dockerfile, and CI
