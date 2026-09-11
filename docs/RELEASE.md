# Story Universe Architect — Release Automation Guide

## The Authoritative Release Command

To package and certify the release:

```bash
python scripts/release.py
```

This single authoritative command builds all release artifacts, updates metadata, and runs isolated verification.

---

## Release Pipeline Stages

1. **Stage 1 — Clean & Validate**:
   - Canonical version extracted from `src/story_universe_architect/__init__.py`.
   - Validates `pyproject.toml`, Skill directory structure, and required sources.
   - Cleans temporary build artifacts safely.

2. **Stage 2 — Run Source Tests**:
   - Executes the complete test suite:
     - `python -m unittest discover -s tests -p "test_*.py"`
     - `node tests/core.test.cjs`
   - Any test failure aborts the release immediately.

3. **Stage 3 — Build Runtime Wheel**:
   - Generates `dist/story_universe_architect_workbench-<version>-py3-none-any.whl`.
   - Bundles pure Python runtime, schema files, and production frontend assets under `story_universe_architect/web/`.

4. **Stage 4 — Update Release Manifests**:
   - Computes SHA-256 digest of the built wheel.
   - Updates `release.json`, `runtime-manifest.json`, and `skills/StoryUniverseArchitect/references/installation.json`.

5. **Stage 5 — Build Skill ZIP**:
   - Packages `skills/StoryUniverseArchitect/` into `dist/StoryUniverseArchitect.zip`.
   - Contains updated checksums from Stage 4.

6. **Stage 6 — Generate Checksums**:
   - Generates root `MANIFEST.sha256` for all produced release artifacts.

7. **Stage 7 — Isolated End-to-End Release Verification**:
   - Runs `scripts/verify_release.py` in an isolated temporary directory.
   - Tests:
     - Wheel installation and package import.
     - CLI `--version` and `--help`.
     - Server startup, `/api/health`, and web asset serving.
     - Workspace creation, validation, and retrieval.
     - Skill ZIP structure and runtime acquisition modes (pre-installed, local dev, verified download).
     - Full roundtrip story submission and targeted patching.
