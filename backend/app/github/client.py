"""A thin ``httpx`` client for the GitHub REST API (ADR-0015).

No SDK. One private ``_request`` handles auth headers, bounded retries on
``429`` / ``5xx`` (honoring ``Retry-After``), transport-error mapping, and the
redacted call log. Every non-2xx status maps to a ``github/errors.py`` type.
"""

from __future__ import annotations

import base64
import time

import httpx

from app.github.errors import (
    GitHubAuthError,
    GitHubConflictError,
    GitHubNetworkError,
    GitHubNotFoundError,
    GitHubPermissionError,
    GitHubRateLimitError,
    GitHubUnavailableError,
)
from app.github.request_log import log_github_call

_API_VERSION = "2022-11-28"


class _PullResult:
    __slots__ = ("url", "number")

    def __init__(self, url: str, number: int) -> None:
        self.url = url
        self.number = number


class GitHubClient:
    def __init__(
        self,
        *,
        token: str | None,
        base_url: str = "https://api.github.com",
        timeout_s: float = 20.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._token = token
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _API_VERSION,
            "User-Agent": "aegis",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout_s,
            transport=transport,
        )
        self._max_retries = max_retries

    # ---------------------------------------------------------------- #

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---------------------------------------------------------------- #

    def _request(self, method: str, path: str, *, json: dict | None = None) -> httpx.Response:
        attempt = 0
        while True:
            started = time.monotonic()
            try:
                resp = self._client.request(method, path, json=json)
            except httpx.TransportError as exc:
                log_github_call(
                    method=method,
                    url=path,
                    status=None,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    outcome="network_error",
                )
                raise GitHubNetworkError(f"network error calling GitHub: {exc}") from exc

            latency_ms = int((time.monotonic() - started) * 1000)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < self._max_retries:
                attempt += 1
                delay = _retry_after_s(resp) or min(2**attempt, 8)
                log_github_call(
                    method=method,
                    url=path,
                    status=resp.status_code,
                    latency_ms=latency_ms,
                    outcome=f"retry_{attempt}",
                )
                time.sleep(delay)
                continue

            log_github_call(
                method=method,
                url=path,
                status=resp.status_code,
                latency_ms=latency_ms,
                outcome="ok" if resp.is_success else "error",
            )
            if not resp.is_success:
                raise _map_status(resp)
            return resp

    # ---- reads ----------------------------------------------------- #

    def get_repo(self, owner: str, repo: str) -> dict:
        return self._request("GET", f"/repos/{owner}/{repo}").json()

    def get_issue(self, owner: str, repo: str, number: int) -> dict:
        return self._request(
            "GET", f"/repos/{owner}/{repo}/issues/{number}"
        ).json()

    def get_ref(self, owner: str, repo: str, ref: str) -> str:
        """Return the commit SHA for ``ref`` (e.g. ``heads/main``)."""
        data = self._request(
            "GET", f"/repos/{owner}/{repo}/git/ref/{ref}"
        ).json()
        return data["object"]["sha"]

    # ---- writes -------------------------------------------------- #

    def create_ref(self, owner: str, repo: str, ref: str, sha: str) -> None:
        """``ref`` is a full ref name, e.g. ``refs/heads/aegis/task-abcd``."""
        self._request(
            "POST",
            f"/repos/{owner}/{repo}/git/refs",
            json={"ref": ref, "sha": sha},
        )

    def put_file(
        self,
        owner: str,
        repo: str,
        path: str,
        *,
        message: str,
        content_bytes: bytes,
        branch: str,
        sha: str | None = None,
    ) -> str:
        """Create/update ``path`` on ``branch`` via the Contents API. Returns
        the resulting commit SHA."""
        body: dict = {
            "message": message,
            "content": base64.b64encode(content_bytes).decode("ascii"),
            "branch": branch,
        }
        if sha is not None:
            body["sha"] = sha
        data = self._request(
            "PUT", f"/repos/{owner}/{repo}/contents/{path}", json=body
        ).json()
        return data["commit"]["sha"]

    def create_pull(
        self,
        owner: str,
        repo: str,
        *,
        title: str,
        head: str,
        base: str,
        body: str,
        draft: bool = True,
    ) -> _PullResult:
        data = self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            json={
                "title": title,
                "head": head,
                "base": base,
                "body": body,
                "draft": draft,
            },
        ).json()
        return _PullResult(url=data["html_url"], number=int(data["number"]))


def _retry_after_s(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


def _map_status(resp: httpx.Response) -> Exception:
    code = resp.status_code
    detail = _short_message(resp)
    if code == 401:
        return GitHubAuthError(f"GitHub authentication failed: {detail}")
    if code == 403:
        # 403 with a rate-limit marker is really a rate limit
        if "rate limit" in detail.lower() or resp.headers.get("X-RateLimit-Remaining") == "0":
            return GitHubRateLimitError("GitHub API rate limit exceeded", github_status=403)
        return GitHubPermissionError(f"GitHub permission denied: {detail}")
    if code == 404:
        return GitHubNotFoundError(f"GitHub resource not found: {detail}")
    if code in (409, 422):
        return GitHubConflictError(f"GitHub conflict: {detail}", github_status=code)
    if code == 429:
        return GitHubRateLimitError("GitHub API rate limit exceeded")
    if code >= 500:
        return GitHubUnavailableError(f"GitHub is unavailable ({code})", github_status=code)
    return GitHubUnavailableError(f"unexpected GitHub status {code}: {detail}", github_status=code)


def _short_message(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("message", ""))[:200]
    except Exception:  # noqa: BLE001
        return resp.text[:200]
