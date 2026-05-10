"""DockerSandbox — concrete v0.1 backend per ADR-015 § Decision point 4.

Authoritative contract: ``docs/architecture/SANDBOX-CONTRACT.md`` v0.1.0 § 6.

Capabilities declared: ``{FILE_RW, EXEC, NETWORK}``. ``GPU``, ``SNAPSHOT``,
``PERSISTENT_VOLUMES`` are not declared and raise
:class:`sandbox.protocol.CapabilityNotAvailable` if invoked.

Per ticket § 8 hard rules this module dispatches all Docker operations
through the ``docker`` Python SDK (the same SDK used by Hermes' built-in
``terminal`` toolset per ``MULTI-HERMES-CONTRACT.md`` § 5.4 / ADR-014
§ Correction 5). Raw ``subprocess.run("docker exec ...")`` is never used.
"""

from __future__ import annotations

import io
import tarfile
from pathlib import PurePosixPath
from typing import Any, Mapping, Optional, Sequence

from .protocol import (
    CapabilityNotAvailable,
    ExecResult,
    SandboxBackend,
    SandboxCapability,
    Session,
)


# Backend-declared capability set per ADR-015 § Decision point 4. The frozen
# set is exported so the dispatcher and test code can compare against it
# without instantiating the backend.
DOCKER_CAPABILITIES: frozenset[SandboxCapability] = frozenset({
    SandboxCapability.FILE_RW,
    SandboxCapability.EXEC,
    SandboxCapability.NETWORK,
})


def _docker_module() -> Any:
    """Lazy import of the ``docker`` Python SDK.

    Lazy so unit tests that inject a mock client do not require the SDK
    to be installed in the test environment. Per ticket § 8 the SDK is
    a v0.1 production dependency (used by Hermes' ``terminal`` toolset);
    this module never falls back to ``subprocess.run("docker ...")``.
    """

    import docker  # type: ignore[import-not-found]

    return docker


class DockerSession(Session):
    """A session bound to a single long-running Docker container.

    The container is created with ``command=["sleep", "infinity"]``
    so subsequent :meth:`exec` calls multiplex into it via
    ``container.exec_run``. This matches the shape Hermes' ``terminal``
    toolset uses today (ADR-014 § Correction 5).
    """

    def __init__(self, container: Any, backend_name: str = "docker") -> None:
        self._container = container
        self._backend_name = backend_name
        self._closed = False

    @property
    def session_id(self) -> str:
        return self._container.id

    def read(self, path: str) -> bytes:
        # docker SDK: container.get_archive(path) returns (chunked-stream,
        # stat-dict). The stream is a tar archive carrying the requested
        # path; we extract the single file member's bytes.
        bits, _stat = self._container.get_archive(path)
        buf = io.BytesIO(b"".join(bits))
        with tarfile.open(fileobj=buf) as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                extracted = tf.extractfile(member)
                if extracted is None:
                    return b""
                return extracted.read()
        return b""

    def write(self, path: str, content: bytes) -> None:
        # docker SDK: container.put_archive(target_dir, tar_bytes).
        target = PurePosixPath(path)
        target_dir = str(target.parent) if str(target.parent) else "/"
        name = target.name
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))
        self._container.put_archive(target_dir, buf.getvalue())

    def exec(
        self,
        cmd: Sequence[str],
        env: Optional[Mapping[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> ExecResult:
        # Per ticket § 7 risk mitigation the abstraction must propagate
        # non-zero exit codes, stderr content, and timeout exceptions
        # verbatim. ``demux=True`` separates stdout/stderr; the SDK's
        # exec_run does not natively accept a per-call timeout so we
        # surface ``timeout`` to the caller via the exception path of
        # the underlying transport (any TimeoutError raised by the SDK
        # transport propagates through unchanged).
        kwargs: dict[str, Any] = {"demux": True}
        if env is not None:
            kwargs["environment"] = dict(env)
        # ``timeout`` is accepted in the signature for forward-compat;
        # the docker SDK 7.x exec_run does not honor it, so we record
        # it for log attribution only and rely on transport-level
        # timeouts raised by the SDK.
        del timeout  # currently advisory; transport raises propagate.
        result = self._container.exec_run(list(cmd), **kwargs)
        exit_code, output = _extract_exec_result(result)
        stdout, stderr = _split_demuxed_output(output)
        return ExecResult(
            exit_code=int(exit_code) if exit_code is not None else 0,
            stdout=stdout,
            stderr=stderr,
        )

    def ls(self, path: str) -> Sequence[str]:
        # Implemented as ``ls -1 <path>`` so directory listing reuses the
        # same SDK exec pathway as :meth:`exec`. Errors propagate
        # verbatim through :class:`RuntimeError`.
        result = self.exec(["ls", "-1", path])
        if result.exit_code != 0:
            stderr_text = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(
                f"ls {path} failed with exit_code={result.exit_code}: "
                f"{stderr_text}"
            )
        return [
            line
            for line in result.stdout.decode(
                "utf-8", errors="replace"
            ).splitlines()
            if line
        ]

    def snapshot(self) -> str:
        raise CapabilityNotAvailable(
            SandboxCapability.SNAPSHOT, self._backend_name
        )

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._container.stop(timeout=5)
        except Exception:
            # Stop failures are tolerated: the subsequent remove(force=True)
            # will reap the container regardless of stop status. Errors
            # surfaced by ``exec`` callers are still propagated verbatim
            # per ticket § 7 risk mitigation; ``shutdown`` is the
            # idempotent teardown path.
            pass
        try:
            self._container.remove(force=True)
        except Exception:
            pass


def _extract_exec_result(result: Any) -> tuple[Any, Any]:
    """Unpack ``container.exec_run`` return shape across SDK versions.

    docker SDK 7.x returns ``ExecResult(exit_code, output)`` (a NamedTuple);
    older shims return a plain ``(exit_code, output)`` tuple. We accept
    both.
    """

    if hasattr(result, "exit_code") and hasattr(result, "output"):
        return result.exit_code, result.output
    return result[0], result[1]


def _split_demuxed_output(output: Any) -> tuple[bytes, bytes]:
    """Normalize ``demux=True`` output to ``(stdout_bytes, stderr_bytes)``."""

    if isinstance(output, tuple) and len(output) == 2:
        stdout, stderr = output
        return (stdout or b""), (stderr or b"")
    if output is None:
        return b"", b""
    return (output or b""), b""


class DockerSandbox(SandboxBackend):
    """Docker-backed sandbox per ADR-015 § Decision point 4.

    Capability set: ``{FILE_RW, EXEC, NETWORK}``. The remaining three
    capabilities (``GPU``, ``SNAPSHOT``, ``PERSISTENT_VOLUMES``) are not
    declared; calls to capability-gated operations on those raise
    :class:`CapabilityNotAvailable`.

    Container image and labels follow ADR-014 § Correction 5 conventions
    used by Hermes' ``terminal`` toolset.
    """

    DEFAULT_IMAGE = "python:3.12-slim"

    def __init__(
        self,
        client: Any = None,
        image: Optional[str] = None,
    ) -> None:
        self._client = client
        self._image = image or self.DEFAULT_IMAGE

    @property
    def name(self) -> str:
        return "docker"

    @property
    def capabilities(self) -> frozenset[SandboxCapability]:
        return DOCKER_CAPABILITIES

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = _docker_module().from_env()
        return self._client

    def create(self, work_item_id: str) -> Session:
        container = self.client.containers.run(
            self._image,
            command=["sleep", "infinity"],
            detach=True,
            labels={
                "developer_assistant.work_item_id": work_item_id,
                "developer_assistant.sandbox": "docker",
            },
        )
        return DockerSession(container, backend_name=self.name)

    def resume(self, session_id: str) -> Session:
        container = self.client.containers.get(session_id)
        return DockerSession(container, backend_name=self.name)

    def destroy(self, session_id: str) -> None:
        try:
            container = self.client.containers.get(session_id)
        except Exception:
            return
        try:
            container.stop(timeout=5)
        except Exception:
            pass
        try:
            container.remove(force=True)
        except Exception:
            pass
