import httpx, os
import time
from dotenv import load_dotenv
import json
from pathlib import Path

load_dotenv()

RATE_LIMIT_MAX_WAIT = 60

DATA_DIR = Path(__file__).parent.parent / "data"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_API_URL = "https://api.github.com"

def save_issues(owner: str, repo: str, issues: list[dict]) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{owner}-{repo}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(issues, f, ensure_ascii=False, indent=2)
    return path

def extract_issue_fields(issue: dict) -> dict:
    return {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "state": issue.get("state"),
        "created_at": issue.get("created_at"),
        "body": issue.get("body"),
        "html_url": issue.get("html_url")
    }

def _rate_limit_wait(response: httpx.Response) -> int | None:
    """Seconds to sleep before retrying, or None if retrying isn't worth it."""
    reset = response.headers.get("x-ratelimit-reset")
    if reset is None:
        return RATE_LIMIT_MAX_WAIT
    wait = int(reset) - int(time.time()) + 1
    return wait if 0 < wait <= RATE_LIMIT_MAX_WAIT else None


def _get_page(url: str, headers: dict, params: dict) -> httpx.Response:
    for attempt in range(2):
        response = httpx.get(url, headers=headers, params=params, timeout=30)
        if response.status_code in (403, 429) and attempt == 0:
            wait = _rate_limit_wait(response)
            if wait is not None:
                print(f"Rate limited, sleeping {wait}s then retrying once")
                time.sleep(wait)
                continue
        break
    response.raise_for_status()
    return response


def fetch_issues(owner: str, repo: str) -> list[dict]:
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}"
    }
    return_issues = []
    per_page = 100
    curr_page = 1
    while True:
        response = _get_page(url, headers, {"per_page": per_page, "page": curr_page, "state": "all"})
        issues = response.json()
        return_issues.extend(issues)
        print(f"Fetched {len(issues)} issues from page {curr_page}")

        curr_page += 1
        if len(issues) < per_page:
            break
    return return_issues


if __name__ == "__main__":
    owner = "pallets"
    repo = "flask"

    start = time.perf_counter()
    issues = fetch_issues(owner, repo)
    save_issues(owner, repo, issues)
    end = time.perf_counter()
    print(f"Time taken: {end - start:.2f} seconds")
    print(len(issues), issues[0]["title"])