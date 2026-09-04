"""SSRF / scheme / host / IDN guard for repository ingestion sources.

See docs/SECURITY_MODEL.md (SSRF threat row), docs/DECISIONS/ADR-0011, ADR-0014,
docs/REPOSITORY_ANALYSIS.md Section 1 ("Validate"). Two independent gates: a remote
https:// URL (GitHub) goes through validate_remote_url; a local filesystem path goes
through validate_local_path. Neither ever executes target-repo code.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from app.core.config import Settings
from app.ingestion.errors import (
    InvalidRepositoryUrlError,
    LocalPathNotAllowedError,
    RepositoryNotFoundError,
    SsrfBlockedError,
)

_OWNER_REPO_PATH = re.compile(r"^/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(\.git)?/?$")


@dataclass(frozen=True)
class ParsedGitHubUrl:
    owner: str
    repo: str
    host: str
    clone_url: str


def _is_ascii(hostname: str) -> bool:
    try:
        hostname.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _reject_idn_homograph(hostname: str) -> None:
    # The remote host allowlist is small and fixed (github.com + operator-configured
    # extras) and none of them are legitimately IDN -- reject any non-ASCII or
    # punycode-looking hostname outright, closing the homograph class without a new
    # confusables-detection dependency.
    if not _is_ascii(hostname) or hostname.startswith("xn--") or ".xn--" in hostname:
        raise InvalidRepositoryUrlError(
            f"hostname {hostname!r} is not a plain ASCII hostname"
        )


def _is_blocked_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def _resolve_all(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise RepositoryNotFoundError(f"could not resolve host {hostname!r}") from exc
    return [ipaddress.ip_address(info[4][0]) for info in infos]


def validate_remote_url(url: str, settings: Settings) -> ParsedGitHubUrl:
    parts = urlsplit(url)

    if parts.scheme != "https":
        raise InvalidRepositoryUrlError(
            f"only https:// URLs are accepted for remote repositories, got scheme {parts.scheme!r}"
        )

    if "@" in (parts.netloc or ""):
        raise InvalidRepositoryUrlError(
            "URLs with embedded credentials are not accepted"
        )

    hostname = (parts.hostname or "").lower()
    if not hostname:
        raise InvalidRepositoryUrlError("URL has no hostname")

    _reject_idn_homograph(hostname)

    allowed = {h.lower() for h in settings.ingestion_allowed_remote_hosts}
    if hostname not in allowed:
        raise InvalidRepositoryUrlError(
            f"host {hostname!r} is not in the allowed hosts list"
        )

    for addr in _resolve_all(hostname):
        if _is_blocked_ip(addr):
            raise SsrfBlockedError(
                f"host {hostname!r} resolves to a disallowed address ({addr})"
            )

    match = _OWNER_REPO_PATH.match(parts.path)
    if not match:
        raise InvalidRepositoryUrlError(
            f"URL path {parts.path!r} is not a valid /owner/repo path"
        )

    owner, repo = match.group("owner"), match.group("repo")
    clone_url = f"https://{hostname}/{owner}/{repo}.git"
    return ParsedGitHubUrl(owner=owner, repo=repo, host=hostname, clone_url=clone_url)


def validate_local_path(raw_path: str, settings: Settings) -> Path:
    resolved = Path(raw_path).resolve()

    roots = [Path(r) for r in settings.ingestion_local_roots]
    if not any(resolved == root or root in resolved.parents for root in roots):
        raise LocalPathNotAllowedError(
            f"path {resolved} is not inside an allowed ingestion root {roots}"
        )

    if not resolved.exists() or not resolved.is_dir():
        raise RepositoryNotFoundError(
            f"local path {resolved} does not exist or is not a directory"
        )

    return resolved
