from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from rq.exceptions import NoSuchJobError
from rq.job import Job
from app.jobs import ingest_repo
from app.queues import ingest_queue, redis_conn

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

@app.get("/health")
def health():
    return {"status": "ok"}

