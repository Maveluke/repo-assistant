import pytest
from rq.exceptions import NoSuchJobError
from rq.job import Job

from app.jobs import ingest_repo
from app.queues import ingest_queue


class FakeJob:
    id = "job-123"


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.parametrize("repo", ["fastapi", "a/b/c", "", "/flask"])
def test_malformed_repo_is_rejected_before_the_handler(client, repo):
    assert client.post("/ingest", json={"repo": repo}).status_code == 422


def test_ingest_enqueues_instead_of_crawling(client, monkeypatch):
    """The endpoint must hand work off, not do it."""
    seen = {}

    def fake_enqueue(func, *args, **kwargs):
        seen["func"] = func
        seen["args"] = args
        return FakeJob()

    monkeypatch.setattr(ingest_queue, "enqueue", fake_enqueue)

    r = client.post("/ingest", json={"repo": "fastapi/fastapi"})

    assert r.status_code == 202
    assert r.json() == {"repo": "fastapi/fastapi", "job_id": "job-123"}
    assert seen["func"] is ingest_repo
    assert seen["args"] == ("fastapi", "fastapi")


def test_unknown_job_id_returns_404(client, monkeypatch):
    def raise_missing(*args, **kwargs):
        raise NoSuchJobError("no such job")

    monkeypatch.setattr(Job, "fetch", raise_missing)

    r = client.get("/jobs/does-not-exist")

    assert r.status_code == 404
    assert r.json() == {"detail": "Job not found"}
