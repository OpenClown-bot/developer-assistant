"""Sandbox capability protocol — Bernstein-style typed abstraction.

Authoritative contract: ``docs/architecture/SANDBOX-CONTRACT.md`` v0.1.0.
Source ADR: ``docs/architecture/adr/ADR-015-sandbox-capability-protocol.md``
v0.1.0.

This package defines the abstract sandbox-backend protocol and the v0.1
concrete ``DockerSandbox`` implementation. The Executor specialist runtime's
``terminal`` toolset is configured to dispatch through the
``SandboxBackend`` selected at runtime; v0.1 ships ``DockerSandbox`` only,
v0.2+ ADRs add ``WorktreeSandbox`` / ``ModalSandbox`` / ``E2BSandbox``
without requiring the specialist runtime config to change shape (per
``MULTI-HERMES-CONTRACT.md`` § 5.4 amendment).
"""

from .docker import DOCKER_CAPABILITIES, DockerSandbox, DockerSession
from .protocol import (
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

__all__ = [
    "CapabilityNotAvailable",
    "DOCKER_CAPABILITIES",
    "DockerSandbox",
    "DockerSession",
    "Err",
    "ExecResult",
    "Ok",
    "Result",
    "SandboxBackend",
    "SandboxCapability",
    "Session",
    "WorkItem",
    "negotiate_capabilities",
]
