from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from rq.exceptions import NoSuchJobError
from rq.job import Job
from app.jobs import ingest_repo
from app.queues import ingest_queue, redis_conn
from app.store import repo_indexed, search

EXCERPT_CHARS = 300

app = FastAPI()

class IngestRequest(BaseModel):
    repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$", description="Repository in the format 'owner/repo'")

class IngestResponse(BaseModel):
    repo: str
    job_id: str

@app.post("/ingest", status_code=202)
def ingest(body: IngestRequest) -> IngestResponse:
    owner, repo = body.repo.split("/")

    job = ingest_queue.enqueue(ingest_repo, owner, repo)

    return IngestResponse(repo=body.repo, job_id=job.id)

@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="Job not found")

    status = job.get_status()
    if status == "finished":
        return {"status": status, "result": job.return_value()}
    elif status == "failed":
        return {"status": status, "error": "Job failed. Check the worker logs for details."}
    else:
        return {"status": status}

class AskRequest(BaseModel):
    repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$", description="Repository in the format 'owner/repo'")
    question: str = Field(min_length=3, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)

class Source(BaseModel):
    number: int
    title: str
    html_url: str
    type: str
    state: str
    distance: float
    excerpt: str

class AskResponse(BaseModel):
    question: str
    sources: list[Source]

@app.post("/ask")
def ask(body: AskRequest) -> AskResponse:
    if not repo_indexed(body.repo):
        raise HTTPException(status_code=404, detail="Repository not indexed. Please ingest the repository first.")

    top_results = search(body.question, body.repo, body.limit)
    sources = [
        Source(
            number=hit["number"],
            title=hit["title"],
            html_url=hit["html_url"],
            type=hit["type"],
            state=hit["state"],
            distance=hit["distance"],
            excerpt=hit["text"][:EXCERPT_CHARS]
        )
        for hit in top_results
    ]
    return AskResponse(question=body.question, sources=sources)

@app.get("/health")
def health():
    return {"status": "ok"}

