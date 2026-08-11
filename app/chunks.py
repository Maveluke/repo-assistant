import json
import re

from app.github import DATA_DIR

# TODO: you write these two.
# MIN_CHARS - below this a chunk is noise ("Fixes #4521"). 200 keeps 95% of issues, 40% of PRs.
# MAX_CHARS - above this you truncate for now, window later. ~4% of records exceed 6000.
MIN_CHARS = 200
MAX_CHARS = 6000


def load_records(owner: str, repo: str) -> list[dict]:
    path = DATA_DIR / f"{owner}-{repo}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_text(record: dict) -> str:
    """The text that gets embedded."""

    title = record.get("title") or ""
    body = record.get("body") or ""
    string = f"{title}\n\n{body}"

    string = re.sub(r"<!--.*?-->", "", string, flags=re.DOTALL)

    return string.strip()




def build_metadata(record: dict, owner: str, repo: str) -> dict:
    """Travels with the chunk but is not embedded. Used for citing and filtering."""

    return {
        "number": record.get("number"),
        "html_url": record.get("html_url"),
        "title": record.get("title"),
        "type": "pull_request" if record.get("pull_request") else "issue",
        "state": record.get("state"),
        "user_login": (record.get("user") or {}).get("login"),
        "repo_whole": f"{owner}/{repo}",
    }



def chunk_records(records: list[dict], owner: str, repo: str) -> list[dict]:
    chunks = []
    for record in records:
        text = build_text(record)

        if len(text) < MIN_CHARS:
            continue

        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS]

        chunks.append({"text": text, **build_metadata(record, owner, repo)})
    return chunks


if __name__ == "__main__":
    owner = "fastapi"
    repo = "fastapi"
    records = load_records(owner, repo)
    chunks = chunk_records(records, owner, repo)
    print(f"{len(records)} records -> {len(chunks)} chunks")
    for chunk in chunks[:3]:
        print(chunk)
