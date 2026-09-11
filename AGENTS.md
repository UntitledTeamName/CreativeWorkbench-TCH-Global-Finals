# Story Universe Architect — Agent Development Guidelines

This document provides instructions for AI agents (including WorkBuddy and Antigravity) working in this repository.

## Architecture Invariants
1. **No Expert Subagents**: The system uses a single WorkBuddy Skill (`skills/StoryUniverseArchitect`). Do not introduce secondary subagent teams or autonomous agent hierarchies inside the runtime.
2. **Deterministic Runtime**: `src/story_universe_architect` is deterministic Python. It handles validation, state persistence, compilers, and web serving.
3. **Turnkey Packaging**: Frontend assets in `src/story_universe_architect/web/` must be bundled into the wheel. Do not produce a separate `web-ui.zip`.
4. **Isolated Release Command**: `python scripts/release.py` is the single authoritative release command. It must build `dist/StoryUniverseArchitect.zip` and `dist/story_universe_architect_workbench-1.1.0-py3-none-any.whl`, synchronize manifests, and pass isolated verification in `scripts/verify_release.py`.
5. **Standard Library Only**: Runtime code must use Python standard library only (no mandatory third-party pip dependencies for running SUA).
