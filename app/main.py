import logging

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from app.github import fetch_issues, save_issues

logger = logging.getLogger(__name__)

app = FastAPI()

class IngestRequest(BaseModel):
    repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$", description="Repository in the format 'owner/repo'")

class IngestResponse(BaseModel):
    repo: str
    count: int

@app.post("/ingest")
def ingest(body: IngestRequest) -> IngestResponse:
    owner, repo = body.repo.split("/")
    try:
        items = fetch_issues(owner, repo)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        logger.warning("GitHub returned %s for %s", status, body.repo)
        if status == 404:
            raise HTTPException(404, f"Repository '{body.repo}' not found") from exc
        if status in (401, 403, 429):
            raise HTTPException(502, "GitHub rejected the request (token or rate limit)") from exc
        raise HTTPException(502, f"GitHub returned {status}") from exc
    except httpx.RequestError as exc:
        logger.warning("Could not reach GitHub for %s: %s", body.repo, exc)
        raise HTTPException(504, "Could not reach GitHub") from exc

    try:
        save_issues(owner, repo, items)
    except OSError as exc:
        logger.exception("Failed writing %s", body.repo)
        raise HTTPException(500, "Failed to write ingested data") from exc

    return {"repo": body.repo, "count": len(items)}

@app.get("/health")
def health():
    return {"status": "ok"}

