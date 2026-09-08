"""SSRF / URL / local-path guard, re-asserted through the Phase 26
``core.security.ssrf`` module path (moved from ``app.ingestion.url_validator``,
which is now a re-export shim).
"""

from __future__ import annotations

import socket

import pytest

from app.core.config import Settings
from app.core.security.ssrf import validate_local_path, validate_remote_url
from app.ingestion.errors import (
    InvalidRepositoryUrlError,
    LocalPathNotAllowedError,
    SsrfBlockedError,
)


@pytest.fixture
def settings(tmp_path) -> Settings:
    (tmp_path / "roots").mkdir()
    return Settings(
        ingestion_local_roots=[str(tmp_path / "roots")],
        ingestion_allowed_remote_hosts=["github.com"],
        _env_file=None,
    )


def test_shim_still_exports_the_names():
    from app.ingestion import url_validator

    assert url_validator.validate_remote_url is validate_remote_url
    assert url_validator.validate_local_path is validate_local_path


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/o/r",  # not https
        "https://gitlab.com/o/r",  # host not allowlisted
        "https://user:pw@github.com/o/r",  # embedded credentials
        "file:///etc/passwd",
        "https://xn--80ak6aa92e.com/o/r",  # IDN homograph
        "https://github.com.evil.com/o/r",  # look-alike host
    ],
)
def test_rejects_bad_remote_urls(url, settings):
    with pytest.raises(InvalidRepositoryUrlError):
        validate_remote_url(url, settings)


def test_blocks_private_ip_via_dns(settings, monkeypatch):
    def fake_getaddrinfo(host, port, *a, **k):
        return [(socket.AF_INET, None, None, None, ("127.0.0.1", port))]

    monkeypatch.setattr("app.core.security.ssrf.socket.getaddrinfo", fake_getaddrinfo)
    with pytest.raises(SsrfBlockedError):
        validate_remote_url("https://github.com/o/r", settings)


def test_blocks_link_local_metadata_ip(settings, monkeypatch):
    def fake_getaddrinfo(host, port, *a, **k):
        return [(socket.AF_INET, None, None, None, ("169.254.169.254", port))]

    monkeypatch.setattr("app.core.security.ssrf.socket.getaddrinfo", fake_getaddrinfo)
    with pytest.raises(SsrfBlockedError):
        validate_remote_url("https://github.com/o/r", settings)


def test_local_path_outside_roots_rejected(settings, tmp_path):
    with pytest.raises(LocalPathNotAllowedError):
        validate_local_path(str(tmp_path / "elsewhere"), settings)


def test_local_path_traversal_out_of_root_rejected(settings, tmp_path):
    inside = tmp_path / "roots"
    with pytest.raises(LocalPathNotAllowedError):
        validate_local_path(str(inside / ".." / ".." / "etc"), settings)
