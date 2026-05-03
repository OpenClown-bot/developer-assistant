---
id: TKT-NEW-006-D
version: 0.1.0
status: backlog
source_tkt: TKT-006
created: 2026-05-03
---

# TKT-NEW-006-D: Implement Filesystem ArtifactWriter

## Context

TKT-006 uses an injectable `ArtifactWriter` protocol and currently passes the directory-like target `docs/questions/`. A real filesystem writer should construct concrete, safe file paths before writing durable decisions.

## Proposed Scope

- Implement a filesystem-backed `ArtifactWriter` for durable founder decisions.
- Generate stable, collision-resistant filenames under `docs/questions/` without raw chat IDs or secret values.
- Include valid YAML frontmatter for created question/decision artifacts if repository validation requires it.
- Add overwrite protection and tests for path traversal, duplicate names, and sanitized content.

## Priority

High before live decision capture writes to disk.
