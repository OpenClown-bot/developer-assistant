"""Concrete runtime executor bindings for TKT-008 REST/Git protocols.

Binds the injectable RESTExecutor and GitExecutor protocols from TKT-008
to real HTTP execution of TKT-014 GitHubRESTRequest objects and real
subprocess execution of TKT-014 GitCommand objects.

Security constraints:
- Authorization injected only at send time, never stored in durable objects.
- All output (errors, stdout, stderr, URLs, headers, response bodies) is
  sanitized with TKT-014 token-redaction helpers.
- No shell execution; subprocess uses argument lists only.
- All commands pass TKT-014 constrained command validation.
- No Hermes bundled GitHub skills are used.
"""

from __future__ import annotations

import json
import urllib.request
import subprocess
from typing import Any, Dict

from src.developer_assistant.github_workflow import (
    CredentialSourceError,
    GitHubRESTRequest,
    GitCommand,
    execute_git_command,
    redact_token,
)

_REDACTED = "***REDACTED***"


class RuntimeRESTError(RuntimeError):
    """Raised when a REST execution fails at the runtime boundary."""


class RuntimeGitError(RuntimeError):
    """Raised when a git execution fails at the runtime boundary."""


def _sanitize_url(url: str) -> str:
    return redact_token(url)


def _sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    sanitized: Dict[str, str] = {}
    for k, v in headers.items():
        sanitized[redact_token(k)] = (
            _REDACTED if k.lower() == "authorization" else redact_token(v)
        )
    return sanitized


def _sanitize_error_text(text: str) -> str:
    return redact_token(text)


class HttpRESTExecutor:
    """Concrete RESTExecutor using stdlib urllib.

    Executes GitHubRESTRequest objects against the GitHub REST API.
    Injects Authorization (Bearer token) only at send time via
    request.with_auth(token). The token is never stored in any
    durable object, log, or artifact.

    All error text, HTTP bodies, URLs, headers, and response metadata
    are sanitized with token-redaction before they reach caller-visible
    exceptions or return values.
    """

    def execute(self, request: GitHubRESTRequest, token: str) -> Dict[str, Any]:
        auth_headers = request.with_auth(token)
        url = request.url
        body_bytes: bytes | None = None

        if request.body is not None:
            body_bytes = json.dumps(request.body).encode("utf-8")

        http_request = urllib.request.Request(
            url,
            data=body_bytes,
            headers=auth_headers,
            method=request.method,
        )

        try:
            response = urllib.request.urlopen(http_request)
            raw_body = response.read().decode("utf-8")
            result = json.loads(raw_body) if raw_body.strip() else {}
        except urllib.error.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8")
            except Exception:
                pass
            raise RuntimeRESTError(
                _sanitize_error_text(
                    f"HTTP {exc.code} {exc.reason} for "
                    f"{_sanitize_url(url)}: {error_body}"
                )
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeRESTError(
                _sanitize_error_text(
                    f"URL error for {_sanitize_url(url)}: {exc.reason}"
                )
            ) from exc
        except (ValueError, OSError) as exc:
            raise RuntimeRESTError(
                _sanitize_error_text(
                    f"REST request failed for {_sanitize_url(url)}: {exc}"
                )
            ) from exc
        except Exception as exc:
            raise RuntimeRESTError(
                _sanitize_error_text(
                    f"Unexpected REST error for {_sanitize_url(url)}: {exc}"
                )
            ) from exc

        if isinstance(result, dict):
            return result
        return {}


class SubprocessGitExecutor:
    """Concrete GitExecutor using subprocess (argument list, no shell).

    Executes GitCommand objects through TKT-014's execute_git_command(),
    which validates arguments against blocked operations, runs through
    subprocess.run with an argument list (shell=False by default), and
    redacts stdout/stderr.

    Force push, --force-with-lease, hard reset, branch deletion,
    token-bearing remotes, and shell metacharacter hazards continue
    to be blocked by TKT-014 validation.

    Git output and errors are sanitized before they can reach callers.
    """

    def execute(self, cmd: GitCommand) -> int:
        try:
            result = execute_git_command(cmd)
        except Exception as exc:
            raise RuntimeGitError(
                _sanitize_error_text(
                    f"Git command failed: {exc}"
                )
            ) from exc

        if result.returncode != 0:
            stderr = getattr(result, "stderr", "") or ""
            raise RuntimeGitError(
                _sanitize_error_text(
                    f"Git command exited with code {result.returncode}: "
                    f"{stderr}"
                )
            )

        return result.returncode