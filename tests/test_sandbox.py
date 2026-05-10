"""Tests for ``src/sandbox`` — protocol shape, DockerSandbox behaviour,
capability negotiation, and verbatim error propagation.

Covers TKT-035 AC-1..AC-4 + AC-3 capability-coverage requirement. The
docker SDK is mocked throughout per ticket § 7 risk-note guidance ("if
absent, fall back to mocked Docker SDK for AC-2 happy-path test"); CI in
this repo runs on a docker-less GitHub Actions runner today.

Uses stdlib ``unittest`` and ``unittest.mock`` only. No real Docker
daemon, no real PATs, no real production hostnames.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sandbox.docker import (  # noqa: E402
    DOCKER_CAPABILITIES,
    DockerSandbox,
    DockerSession,
)
from sandbox.protocol import (  # noqa: E402
    CapabilityNotAvailable,
    Err,
    ExecResult,
    Ok,
    Result,
    SandboxBackend,
    SandboxCapability,
    Session,
    WorkItem,
    negotiate_capabilities,
)


class CapabilityEnumTests(unittest.TestCase):
    """AC-1: enum has exactly six values matching ADR-015 § Decision 1."""

    def test_exactly_six_values_in_adr_order(self) -> None:
        self.assertEqual(
            [c.name for c in SandboxCapability],
            [
                "FILE_RW",
                "EXEC",
                "NETWORK",
                "GPU",
                "SNAPSHOT",
                "PERSISTENT_VOLUMES",
            ],
        )

    def test_value_matches_name(self) -> None:
        for cap in SandboxCapability:
            self.assertEqual(cap.value, cap.name)

    def test_enum_is_a_set_of_six(self) -> None:
        self.assertEqual(len(set(SandboxCapability)), 6)


class ProtocolShapeTests(unittest.TestCase):
    """AC-1, AC-4: ABC method-presence enforcement on backend + session."""

    def test_sandbox_backend_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            SandboxBackend()  # type: ignore[abstract]

    def test_session_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            Session()  # type: ignore[abstract]

    def test_partial_backend_implementation_remains_abstract(self) -> None:
        class HalfBackend(SandboxBackend):
            @property
            def name(self) -> str:
                return "half"

            # capabilities/create/resume/destroy intentionally missing.

        with self.assertRaises(TypeError):
            HalfBackend()  # type: ignore[abstract]

    def test_partial_session_implementation_remains_abstract(self) -> None:
        class HalfSession(Session):
            @property
            def session_id(self) -> str:
                return "x"

            # read/write/exec/ls/snapshot/shutdown intentionally missing.

        with self.assertRaises(TypeError):
            HalfSession()  # type: ignore[abstract]

    def test_concrete_backend_lists_required_methods(self) -> None:
        # Spot-check that the abstract methods named in ADR-015 §
        # Decision 2 are declared on the ABCs as abstract.
        backend_required = {
            "name",
            "capabilities",
            "create",
            "resume",
            "destroy",
        }
        session_required = {
            "session_id",
            "read",
            "write",
            "exec",
            "ls",
            "snapshot",
            "shutdown",
        }
        self.assertTrue(
            backend_required.issubset(set(SandboxBackend.__abstractmethods__))
        )
        self.assertTrue(
            session_required.issubset(set(Session.__abstractmethods__))
        )


class _StubBackend(SandboxBackend):
    """Test backend that declares an arbitrary capability set."""

    def __init__(self, declared: frozenset[SandboxCapability]) -> None:
        self._declared = declared

    @property
    def name(self) -> str:
        return "stub"

    @property
    def capabilities(self) -> frozenset[SandboxCapability]:
        return self._declared

    def create(self, work_item_id: str) -> Session:
        raise NotImplementedError

    def resume(self, session_id: str) -> Session:
        raise NotImplementedError

    def destroy(self, session_id: str) -> None:
        raise NotImplementedError


class NegotiationTests(unittest.TestCase):
    """AC-3: ``negotiate_capabilities`` returns ``Ok`` / ``Err``."""

    def setUp(self) -> None:
        self.backend = _StubBackend(DOCKER_CAPABILITIES)

    def test_ok_when_all_required_caps_declared(self) -> None:
        wi = WorkItem(
            required_capabilities=frozenset({SandboxCapability.EXEC})
        )
        result: Result = negotiate_capabilities(wi, self.backend)
        self.assertIsInstance(result, Ok)

    def test_ok_when_no_required_caps(self) -> None:
        wi = WorkItem()
        result = negotiate_capabilities(wi, self.backend)
        self.assertIsInstance(result, Ok)

    def test_ok_when_required_subset_of_declared(self) -> None:
        wi = WorkItem(
            required_capabilities=frozenset({
                SandboxCapability.FILE_RW,
                SandboxCapability.EXEC,
                SandboxCapability.NETWORK,
            }),
        )
        result = negotiate_capabilities(wi, self.backend)
        self.assertIsInstance(result, Ok)

    def test_err_when_missing_cap(self) -> None:
        wi = WorkItem(
            required_capabilities=frozenset({SandboxCapability.GPU})
        )
        result = negotiate_capabilities(wi, self.backend)
        self.assertIsInstance(result, Err)
        assert isinstance(result, Err)
        self.assertEqual(result.missing_capability, SandboxCapability.GPU)

    def test_err_for_each_unsupported_capability(self) -> None:
        # AC-3 explicit requirement: cover all six capabilities.
        for cap in SandboxCapability:
            wi = WorkItem(required_capabilities=frozenset({cap}))
            result = negotiate_capabilities(wi, self.backend)
            if cap in self.backend.capabilities:
                self.assertIsInstance(
                    result, Ok, f"{cap.name} should be declared"
                )
            else:
                self.assertIsInstance(
                    result, Err, f"{cap.name} should be missing"
                )
                assert isinstance(result, Err)
                self.assertEqual(result.missing_capability, cap)

    def test_err_against_empty_backend(self) -> None:
        empty = _StubBackend(frozenset())
        for cap in SandboxCapability:
            wi = WorkItem(required_capabilities=frozenset({cap}))
            result = negotiate_capabilities(wi, empty)
            self.assertIsInstance(result, Err)
            assert isinstance(result, Err)
            self.assertEqual(result.missing_capability, cap)


class DockerSandboxCapabilityTests(unittest.TestCase):
    """AC-2: capability declaration is exactly ``{FILE_RW, EXEC, NETWORK}``."""

    def test_declares_only_file_rw_exec_network(self) -> None:
        sandbox = DockerSandbox(client=MagicMock())
        self.assertEqual(
            sandbox.capabilities,
            frozenset({
                SandboxCapability.FILE_RW,
                SandboxCapability.EXEC,
                SandboxCapability.NETWORK,
            }),
        )

    def test_module_level_constant_matches_instance(self) -> None:
        self.assertEqual(
            DOCKER_CAPABILITIES,
            frozenset({
                SandboxCapability.FILE_RW,
                SandboxCapability.EXEC,
                SandboxCapability.NETWORK,
            }),
        )

    def test_does_not_declare_gpu_snapshot_or_persistent_volumes(self) -> None:
        sandbox = DockerSandbox(client=MagicMock())
        for forbidden in (
            SandboxCapability.GPU,
            SandboxCapability.SNAPSHOT,
            SandboxCapability.PERSISTENT_VOLUMES,
        ):
            self.assertNotIn(forbidden, sandbox.capabilities)

    def test_name_is_docker(self) -> None:
        sandbox = DockerSandbox(client=MagicMock())
        self.assertEqual(sandbox.name, "docker")


def _make_exec_result(
    exit_code: int, stdout: bytes = b"", stderr: bytes = b""
) -> MagicMock:
    """Build a ``container.exec_run`` return value mimicking docker
    SDK 7.x's ``ExecResult(exit_code, output)`` shape with ``demux=True``.
    """

    res = MagicMock()
    res.exit_code = exit_code
    res.output = (stdout, stderr)
    return res


class DockerSandboxHappyPathTests(unittest.TestCase):
    """AC-2: create -> exec -> shutdown happy path with mocked SDK."""

    def setUp(self) -> None:
        self.client = MagicMock()
        self.container = MagicMock()
        self.container.id = "container-abc"
        self.client.containers.run.return_value = self.container
        self.client.containers.get.return_value = self.container
        self.sandbox = DockerSandbox(
            client=self.client, image="python:3.12-slim"
        )

    def test_create_runs_container_with_sleep_infinity(self) -> None:
        session = self.sandbox.create("TKT-035-wi-1")
        self.client.containers.run.assert_called_once()
        args, kwargs = self.client.containers.run.call_args
        self.assertEqual(args[0], "python:3.12-slim")
        self.assertEqual(kwargs["command"], ["sleep", "infinity"])
        self.assertTrue(kwargs["detach"])
        self.assertEqual(
            kwargs["labels"]["developer_assistant.work_item_id"],
            "TKT-035-wi-1",
        )
        self.assertEqual(
            kwargs["labels"]["developer_assistant.sandbox"], "docker"
        )
        self.assertEqual(session.session_id, "container-abc")
        self.assertIsInstance(session, DockerSession)

    def test_exec_returns_exec_result_with_stdout(self) -> None:
        self.container.exec_run.return_value = _make_exec_result(
            0, stdout=b"hello\n"
        )
        session = self.sandbox.create("wi")
        outcome = session.exec(["echo", "hello"])
        self.container.exec_run.assert_called_once()
        args, kwargs = self.container.exec_run.call_args
        self.assertEqual(args[0], ["echo", "hello"])
        self.assertTrue(kwargs.get("demux"))
        self.assertIsInstance(outcome, ExecResult)
        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(outcome.stdout, b"hello\n")
        self.assertEqual(outcome.stderr, b"")

    def test_exec_passes_environment_through(self) -> None:
        self.container.exec_run.return_value = _make_exec_result(
            0, stdout=b""
        )
        session = self.sandbox.create("wi")
        session.exec(["env"], env={"FOO": "bar"})
        _, kwargs = self.container.exec_run.call_args
        self.assertEqual(kwargs.get("environment"), {"FOO": "bar"})

    def test_resume_returns_session_for_existing_container(self) -> None:
        session = self.sandbox.resume("container-abc")
        self.client.containers.get.assert_called_once_with("container-abc")
        self.assertEqual(session.session_id, "container-abc")

    def test_shutdown_stops_and_removes(self) -> None:
        session = self.sandbox.create("wi")
        session.shutdown()
        self.container.stop.assert_called_once()
        self.container.remove.assert_called_once_with(force=True)

    def test_shutdown_is_idempotent(self) -> None:
        session = self.sandbox.create("wi")
        session.shutdown()
        session.shutdown()
        self.container.stop.assert_called_once()
        self.container.remove.assert_called_once_with(force=True)

    def test_destroy_stops_and_removes(self) -> None:
        self.sandbox.destroy("container-abc")
        self.client.containers.get.assert_called_once_with("container-abc")
        self.container.stop.assert_called_once()
        self.container.remove.assert_called_once_with(force=True)

    def test_destroy_is_safe_when_container_missing(self) -> None:
        self.client.containers.get.side_effect = RuntimeError("no such container")
        # destroy() must not raise on missing-container teardown.
        self.sandbox.destroy("container-missing")
        self.container.stop.assert_not_called()


class DockerSandboxErrorPropagationTests(unittest.TestCase):
    """AC-4 + ticket § 7: exec must propagate non-zero exit / stderr /
    timeout exceptions verbatim. The abstraction layer must not mask
    Docker-side errors that the Executor previously saw directly."""

    def setUp(self) -> None:
        self.client = MagicMock()
        self.container = MagicMock()
        self.container.id = "container-err"
        self.client.containers.run.return_value = self.container
        self.sandbox = DockerSandbox(client=self.client)
        self.session = self.sandbox.create("wi-err")

    def test_exec_propagates_nonzero_exit_code_verbatim(self) -> None:
        self.container.exec_run.return_value = _make_exec_result(
            17, stdout=b"", stderr=b"boom\n"
        )
        outcome = self.session.exec(["false"])
        self.assertEqual(outcome.exit_code, 17)
        self.assertEqual(outcome.stderr, b"boom\n")

    def test_exec_propagates_stderr_verbatim(self) -> None:
        self.container.exec_run.return_value = _make_exec_result(
            2,
            stdout=b"",
            stderr=b"compilation failed: error E001\n",
        )
        outcome = self.session.exec(["make"])
        self.assertEqual(outcome.exit_code, 2)
        self.assertEqual(
            outcome.stderr, b"compilation failed: error E001\n"
        )

    def test_exec_propagates_timeout_exception_verbatim(self) -> None:
        # The docker SDK raises its own exception class on transport
        # timeouts. We verify with stdlib ``TimeoutError`` to keep the
        # test independent of the SDK's import path; the contract is
        # that whatever the SDK raises propagates unchanged.
        self.container.exec_run.side_effect = TimeoutError("read timed out")
        with self.assertRaises(TimeoutError) as ctx:
            self.session.exec(["sleep", "60"], timeout=0.1)
        self.assertEqual(str(ctx.exception), "read timed out")

    def test_exec_propagates_arbitrary_sdk_exception_verbatim(self) -> None:
        class FakeAPIError(Exception):
            """Stand-in for ``docker.errors.APIError``."""

        self.container.exec_run.side_effect = FakeAPIError(
            "500 Server Error: Internal Server Error"
        )
        with self.assertRaises(FakeAPIError) as ctx:
            self.session.exec(["whatever"])
        self.assertIn("500 Server Error", str(ctx.exception))

    def test_ls_raises_runtime_error_with_stderr_on_nonzero_exit(
        self,
    ) -> None:
        self.container.exec_run.return_value = _make_exec_result(
            2, stdout=b"", stderr=b"ls: cannot access '/missing'\n"
        )
        with self.assertRaises(RuntimeError) as ctx:
            self.session.ls("/missing")
        self.assertIn("/missing", str(ctx.exception))
        self.assertIn("ls: cannot access", str(ctx.exception))


class CapabilityNotAvailableTests(unittest.TestCase):
    """AC-2 + AC-4: snapshot raises CapabilityNotAvailable on Docker;
    exception carries the requested capability and backend name."""

    def setUp(self) -> None:
        self.client = MagicMock()
        self.container = MagicMock()
        self.container.id = "c1"
        self.client.containers.run.return_value = self.container
        self.sandbox = DockerSandbox(client=self.client)

    def test_snapshot_raises_capability_not_available(self) -> None:
        session = self.sandbox.create("wi")
        with self.assertRaises(CapabilityNotAvailable) as ctx:
            session.snapshot()
        self.assertEqual(
            ctx.exception.capability, SandboxCapability.SNAPSHOT
        )
        self.assertEqual(ctx.exception.backend_name, "docker")

    def test_exception_message_names_capability_and_backend(self) -> None:
        exc = CapabilityNotAvailable(SandboxCapability.GPU, "docker")
        self.assertIn("GPU", str(exc))
        self.assertIn("docker", str(exc))

    def test_exception_message_omits_suffix_without_backend(self) -> None:
        exc = CapabilityNotAvailable(SandboxCapability.PERSISTENT_VOLUMES)
        self.assertIn("PERSISTENT_VOLUMES", str(exc))
        self.assertNotIn("on backend", str(exc))


class FileRoundTripTests(unittest.TestCase):
    """AC-2: write/read use docker SDK ``put_archive`` / ``get_archive``
    rather than raw ``subprocess.run`` (ticket § 8 hard rule)."""

    def setUp(self) -> None:
        self.client = MagicMock()
        self.container = MagicMock()
        self.container.id = "c2"
        self.client.containers.run.return_value = self.container
        self.sandbox = DockerSandbox(client=self.client)
        self.session = self.sandbox.create("wi")

    def test_write_calls_put_archive(self) -> None:
        self.session.write("/work/hello.txt", b"hi\n")
        self.container.put_archive.assert_called_once()
        args, _ = self.container.put_archive.call_args
        target_dir, tar_bytes = args
        self.assertEqual(target_dir, "/work")
        self.assertIsInstance(tar_bytes, (bytes, bytearray))
        self.assertGreater(len(tar_bytes), 0)

    def test_read_calls_get_archive(self) -> None:
        # Build a minimal tar stream containing one file with ``b"hi\n"``.
        import io
        import tarfile

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            info = tarfile.TarInfo(name="hello.txt")
            payload = b"hi\n"
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))

        self.container.get_archive.return_value = (
            iter([buf.getvalue()]),
            {"size": len(buf.getvalue())},
        )

        content = self.session.read("/work/hello.txt")
        self.container.get_archive.assert_called_once_with(
            "/work/hello.txt"
        )
        self.assertEqual(content, b"hi\n")


if __name__ == "__main__":
    unittest.main()
