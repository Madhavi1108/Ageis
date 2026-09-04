"""Policy/flag assertions -- no Docker daemon required, this only inspects
the dict passed to the docker SDK."""

from aegis.sandbox.policy import ResourceLimits, build_run_kwargs


def _kwargs(**overrides):
    base = dict(image="img", command=["pytest"], workspace_host_path="/tmp/ws")
    base.update(overrides)
    return build_run_kwargs(**base)


def test_network_is_disabled():
    assert _kwargs()["network_mode"] == "none"


def test_all_capabilities_dropped():
    assert _kwargs()["cap_drop"] == ["ALL"]


def test_no_new_privileges():
    assert "no-new-privileges" in _kwargs()["security_opt"]


def test_pids_limit_set():
    limits = ResourceLimits(pids_limit=123)
    assert _kwargs(limits=limits)["pids_limit"] == 123


def test_memory_and_cpu_caps_set():
    limits = ResourceLimits(memory_mb=512, cpus=1.0)
    kwargs = _kwargs(limits=limits)
    assert kwargs["mem_limit"] == "512m"
    assert kwargs["memswap_limit"] == "512m"
    assert kwargs["nano_cpus"] == 1_000_000_000


def test_readonly_rootfs_with_tmpfs_scratch():
    kwargs = _kwargs()
    assert kwargs["read_only"] is True
    assert "/tmp" in kwargs["tmpfs"]


def test_non_root_user():
    assert _kwargs()["user"] != "root" and _kwargs()["user"] != "0:0"


def test_no_docker_socket_ever_mounted():
    kwargs = _kwargs()
    for vol in kwargs["volumes"]:
        assert "docker.sock" not in vol


def test_only_workspace_is_mounted_readwrite():
    kwargs = _kwargs(workspace_host_path="/host/ws")
    assert kwargs["volumes"] == {"/host/ws": {"bind": "/workspace", "mode": "rw"}}


def test_env_allowlist_drops_unlisted_keys():
    kwargs = _kwargs(
        extra_env={"PATH": "/usr/bin", "AWS_SECRET_ACCESS_KEY": "shh", "LANG": "C"}
    )
    assert "AWS_SECRET_ACCESS_KEY" not in kwargs["environment"]
    assert "PATH" not in kwargs["environment"]  # not in the allowlist either
    assert kwargs["environment"]["LANG"] == "C"
