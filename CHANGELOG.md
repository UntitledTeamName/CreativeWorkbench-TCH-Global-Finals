# Changelog

All notable changes to Story Universe Architect will be documented in this file.

## [1.1.0] - 2026-09-11

### Architectural Overhaul & Migration
- **Decoupled from Expert Team**: Removed the multi-role expert architecture (`story-universe-architect-team-team-lead`, `story-architect`, `relationship-mapper`).
- **WorkBuddy Skill Integration**: Created standalone `StoryUniverseArchitect` Skill with conversational input collection, single-pass initial generation, and natural-language targeted editing.
- **Standalone Localhost Runtime**: Packaged the Python server, canonical Draft 2020-12 data model, deterministic compilers, and persistent workspace manager into `story_universe_architect_workbench`.
- **Turnkey Wheel Packaging**: Inlined production web assets (`web/index.html`, `style.css`, `app.js`, `core.js`) into the runtime wheel. No separate frontend ZIP required.
- **Three Runtime Acquisition Modes**: Added support for local development source, pre-installed wheel, and verified automatic release download with SHA-256 integrity verification.
- **Authoritative Release Automation**: Implemented `scripts/release.py` and `scripts/verify_release.py` to certify the release artifacts deterministically.
