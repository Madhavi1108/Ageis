import socket

import pytest

from app.core.config import Settings
from app.ingestion.errors import (
    InvalidRepositoryUrlError,
    LocalPathNotAllowedError,
    RepositoryNotFoundError,
    SsrfBlockedError,
)
from app.ingestion.url_validator import validate_local_path, validate_remote_url


@pytest.fixture
def settings():
    return Settings(_env_file=None)


def test_accepts_valid_github_https_url(settings):
    parsed = validate_remote_url("https://github.com/octocat/hello-world", settings)
    assert parsed.owner == "octocat"
    assert parsed.repo == "hello-world"
    assert parsed.clone_url == "https://github.com/octocat/hello-world.git"


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:octocat/hello-world.git",
        "ssh://git@github.com/octocat/hello-world.git",
        "file:///etc/passwd",
        "http://github.com/octocat/hello-world",  # not https
        "https://user:pass@github.com/octocat/hello-world",  # embedded creds
        "https://github.com/",  # no owner/repo
    ],
)
def test_rejects_malformed_or_wrong_scheme_urls(settings, url):
    with pytest.raises(InvalidRepositoryUrlError):
        validate_remote_url(url, settings)


def test_rejects_disallowed_host(settings):
    with pytest.raises(InvalidRepositoryUrlError):
        validate_remote_url("https://github.com.evil.com/octocat/hello-world", settings)


def test_rejects_idn_homograph_host(settings):
    with pytest.raises(InvalidRepositoryUrlError):
        validate_remote_url("https://xn--gthub-n2a.com/octocat/hello-world", settings)


def test_rejects_localhost_via_ssrf_guard(settings, monkeypatch):
    settings = Settings(ingestion_allowed_remote_hosts=["localhost"], _env_file=None)

    def fake_getaddrinfo(host, port, **kwargs):
        return [(socket.AF_INET, None, None, None, ("127.0.0.1", port))]

    monkeypatch.setattr(
        "app.ingestion.url_validator.socket.getaddrinfo", fake_getaddrinfo
    )
    with pytest.raises(SsrfBlockedError):
        validate_remote_url("https://localhost/octocat/hello-world", settings)


def test_rejects_link_local_metadata_ip_via_dns_rebinding(settings, monkeypatch):
    settings = Settings(ingestion_allowed_remote_hosts=["evil.example"], _env_file=None)

    def fake_getaddrinfo(host, port, **kwargs):
        return [(socket.AF_INET, None, None, None, ("169.254.169.254", port))]

    monkeypatch.setattr(
        "app.ingestion.url_validator.socket.getaddrinfo", fake_getaddrinfo
    )
    with pytest.raises(SsrfBlockedError):
        validate_remote_url("https://evil.example/octocat/hello-world", settings)


def test_unresolvable_host_raises_not_found(settings, monkeypatch):
    def fake_getaddrinfo(host, port, **kwargs):
        raise socket.gaierror("unknown host")

    monkeypatch.setattr(
        "app.ingestion.url_validator.socket.getaddrinfo", fake_getaddrinfo
    )
    with pytest.raises(RepositoryNotFoundError):
        validate_remote_url("https://github.com/octocat/hello-world", settings)


def test_local_path_inside_root_accepted(settings, tmp_path):
    settings = Settings(ingestion_local_roots=[str(tmp_path)], _env_file=None)
    target = tmp_path / "repo"
    target.mkdir()
    resolved = validate_local_path(str(target), settings)
    assert resolved == target.resolve()


def test_local_path_traversal_rejected(settings, tmp_path):
    settings = Settings(ingestion_local_roots=[str(tmp_path / "roots")], _env_file=None)
    (tmp_path / "roots").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(LocalPathNotAllowedError):
        validate_local_path(str(outside), settings)


def test_local_path_must_exist(settings, tmp_path):
    settings = Settings(ingestion_local_roots=[str(tmp_path)], _env_file=None)
    with pytest.raises(RepositoryNotFoundError):
        validate_local_path(str(tmp_path / "does-not-exist"), settings)
