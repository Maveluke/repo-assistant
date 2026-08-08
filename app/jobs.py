from app.github import fetch_issues, save_issues


def ingest_repo(owner: str, repo: str) -> dict:
    issues = fetch_issues(owner, repo)
    save_issues(owner, repo, issues)
    return {
        "owner": owner,
        "repo": repo,
        "records_count": len(issues), 
    }