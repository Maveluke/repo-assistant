import time

import httpx
import respx

from app.github import fetch_issues

ISSUES_URL = "https://api.github.com/repos/fake/repo/issues"


@respx.mock
def test_pagination_stops_on_short_page(issue_page):
    route = respx.get(ISSUES_URL).mock(
        side_effect=[
            httpx.Response(200, json=issue_page(100)),
            httpx.Response(200, json=issue_page(100)),
            httpx.Response(200, json=issue_page(47)),
        ]
    )

    items = fetch_issues("fake", "repo")

    assert len(items) == 247
    assert route.call_count == 3
    requested_pages = [c.request.url.params["page"] for c in route.calls]
    assert requested_pages == ["1", "2", "3"]


@respx.mock
def test_exact_multiple_of_page_size_needs_one_more_request(issue_page):
    """A repo with exactly 100 records still costs a second, empty request."""
    route = respx.get(ISSUES_URL).mock(
        side_effect=[
            httpx.Response(200, json=issue_page(100)),
            httpx.Response(200, json=[]),
        ]
    )

    items = fetch_issues("fake", "repo")

    assert len(items) == 100
    assert route.call_count == 2


@respx.mock
def test_retries_once_after_rate_limit(issue_page, monkeypatch):
    slept = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    reset_at = str(int(time.time()) + 5)
    route = respx.get(ISSUES_URL).mock(
        side_effect=[
            httpx.Response(403, headers={"x-ratelimit-reset": reset_at}),
            httpx.Response(200, json=issue_page(3)),
        ]
    )

    items = fetch_issues("fake", "repo")

    assert len(items) == 3
    assert route.call_count == 2
    assert slept and 0 < slept[0] <= 60


@respx.mock
def test_gives_up_when_reset_is_too_far_away(issue_page, monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)

    reset_at = str(int(time.time()) + 3600)
    respx.get(ISSUES_URL).mock(
        return_value=httpx.Response(403, headers={"x-ratelimit-reset": reset_at})
    )

    try:
        fetch_issues("fake", "repo")
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 403
    else:
        raise AssertionError("expected HTTPStatusError")
