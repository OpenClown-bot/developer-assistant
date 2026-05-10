"""Sandbox capability protocol — abstract interfaces.

Authoritative contract: ``docs/architecture/SANDBOX-CONTRACT.md`` v0.1.0.
Source ADR: ``docs/architecture/adr/ADR-015-sandbox-capability-protocol.md``
v0.1.0.

This module is the abstraction layer between the Executor specialist
runtime's Hermes ``terminal`` toolset and a concrete sandbox backend.
The protocol is intentionally thin (one enum, two ABCs, one Result
type, one pure helper) so the v0.1 single-backend deployment carries
no functional cost over the previous direct-Docker wiring while v0.2+
backend additions remain non-breaking.

Vocabulary follows Bernstein's reference implementation
(``bernstein@f950c71eddf0:docs/architecture/sandbox.md:L21-L91``);
adoption rationale in ARCH-002 § 3.6 and ADR-015 § Decision points 1-6.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Sequence, Union


class SandboxCapability(Enum):
    """Finite capability tags per ADR-015 § Decision point 1.

    A backend declares the subset it supports via ``SandboxBackend.capabilities``.
    The dispatcher compares that set against a work item's
    ``required_capabilities`` (declared in ticket frontmatter) at dispatch
    time via :func:`negotiate_capabilities`.

    The six values here are exhaustive and frozen for v0.1; additions
    require an ADR amendment to ADR-015 per ticket § 8 hard rules.
    """

    FILE_RW = "FILE_RW"
    EXEC = "EXEC"
    NETWORK = "NETWORK"
    GPU = "GPU"
    SNAPSHOT = "SNAPSHOT"
    PERSISTENT_VOLUMES = "PERSISTENT_VOLUMES"


class CapabilityNotAvailable(Exception):
    """Raised when an unsupported capability operation is invoked at runtime.

    Negotiation (:func:`negotiate_capabilities`) catches mismatches *at
    dispatch time*. This exception is the runtime counterpart for code
    paths that bypass negotiation (for example, a direct call to
    ``Session.snapshot`` on a backend that does not declare
    :attr:`SandboxCapability.SNAPSHOT`).
    """

    def __init__(
        self,
        capability: "SandboxCapability",
        backend_name: str = "",
    ) -> None:
        self.capability = capability
        self.backend_name = backend_name
        suffix = f" on backend {backend_name!r}" if backend_name else ""
        super().__init__(
            f"Capability {capability.name} not available{suffix}."
        )


@dataclass(frozen=True)
class WorkItem:
    """Minimal work-item shape consumed by :func:`negotiate_capabilities`.

    Real work items in the operational store carry many more fields
    (see ``OPERATIONAL-STATE-STORE.md`` § 3.5). For sandbox negotiation
    only ``required_capabilities`` is load-bearing; ``id`` is included
    for log-line attribution.
    """

    required_capabilities: frozenset[SandboxCapability] = field(
        default_factory=frozenset
    )
    id: Optional[str] = None


@dataclass(frozen=True)
class Ok:
    """Successful negotiation result."""


@dataclass(frozen=True)
class Err:
    """Negotiation error.

    ``missing_capability`` is the first capability the work item required
    that the backend does not declare. Per ADR-015 § Decision point 3 the
    dispatcher refuses to dispatch on ``Err`` and emits a ``mail``-modality
    escalation (per ADR-017) naming the missing capability.
    """

    missing_capability: SandboxCapability


Result = Union[Ok, Err]


@dataclass(frozen=True)
class ExecResult:
    """Outcome of :meth:`Session.exec`.

    Per ticket § 7 risk mitigation the abstraction layer must not mask
    Docker-side errors: ``exit_code`` is the verbatim process exit
    status, ``stdout`` and ``stderr`` are bytes (not str-decoded) so
    binary build output passes through faithfully.
    """

    exit_code: int
    stdout: bytes
    stderr: bytes


class Session(ABC):
    """An active sandbox session.

    Sessions are created by :meth:`SandboxBackend.create` or re-attached
    by :meth:`SandboxBackend.resume`. ``session_id`` is opaque to the
    caller; the backend manages identity (for the Docker backend this
    is the container id).
    """

    @property
    @abstractmethod
    def session_id(self) -> str:
        """The opaque session identifier."""

    @abstractmethod
    def read(self, path: str) -> bytes:
        """Read file contents from inside the sandbox."""

    @abstractmethod
    def write(self, path: str, content: bytes) -> None:
        """Write file contents into the sandbox."""

    @abstractmethod
    def exec(
        self,
        cmd: Sequence[str],
        env: Optional[Mapping[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> ExecResult:
        """Execute ``cmd`` inside the sandbox.

        Implementations MUST propagate non-zero exit codes, stderr
        content, and timeout exceptions verbatim to the caller per
        ticket § 7 risk mitigation. The abstraction layer must never
        swallow or rewrite a Docker-side error.
        """

    @abstractmethod
    def ls(self, path: str) -> Sequence[str]:
        """List directory entries under ``path`` inside the sandbox."""

    @abstractmethod
    def snapshot(self) -> str:
        """Capture a session snapshot.

        Capability-gated. Implementations whose backend does not declare
        :attr:`SandboxCapability.SNAPSHOT` raise :class:`CapabilityNotAvailable`.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """Tear down the session. Must be idempotent."""


class SandboxBackend(ABC):
    """Abstract sandbox backend per ADR-015 § Decision point 2.

    A backend declares its supported capability subset and exposes the
    create / resume / destroy lifecycle that produces :class:`Session`
    instances. v0.1 ships exactly one concrete backend
    (:class:`sandbox.docker.DockerSandbox`); v0.2+ ADRs add new backends
    without requiring changes to the specialist runtime configuration.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier, e.g. ``'docker'``."""

    @property
    @abstractmethod
    def capabilities(self) -> frozenset[SandboxCapability]:
        """The capability set this backend declares it supports."""

    @abstractmethod
    def create(self, work_item_id: str) -> Session:
        """Create a fresh session bound to ``work_item_id``."""

    @abstractmethod
    def resume(self, session_id: str) -> Session:
        """Re-attach to an existing session by id."""

    @abstractmethod
    def destroy(self, session_id: str) -> None:
        """Destroy a session by id. Must be idempotent."""


def negotiate_capabilities(
    work_item: WorkItem, backend: SandboxBackend
) -> Result:
    """Pure-function dispatch-time capability negotiation.

    Compares ``work_item.required_capabilities`` against
    ``backend.capabilities``. Returns:

    - :class:`Ok` if every required capability is declared by the backend.
    - :class:`Err` carrying the first required-but-undeclared capability.

    Per ADR-015 § Decision point 3 the dispatcher refuses to dispatch
    on :class:`Err` and emits a ``mail``-modality escalation (per ADR-017)
    naming the missing capability.

    The function is pure and free of I/O so it can be exercised
    transparently in tests and called from any runtime.
    """

    declared = backend.capabilities
    for required in work_item.required_capabilities:
        if required not in declared:
            return Err(missing_capability=required)
    return Ok()
