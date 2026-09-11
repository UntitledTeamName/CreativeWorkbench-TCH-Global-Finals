# CharacterOS

**CharacterOS** is an offline-first, localhost-first creative writing workbench and narrative compiler. Part of [CharacterOS: Creative Workbench for Workbuddy](https://github.com/mrc2rules/CharacterOS). It transforms a single premise into a fully connected, structurally sound story universe with cast profiles, asymmetric relationship maps, narrative gap additions, a 4-category visual prompt kit, and directional story seeds.

---

## Architecture & Lifecycle Overview

The skill follows a strict **prompt-first lifecycle**:
1. Conversational input gathering occurs **first** before runtime acquisition or generation.
2. All required answers are collected conversationally.
3. Cryptographically verified runtime is acquired or updated from Git (`https://github.com/mrc2rules/CharacterOS.git`).
4. Story universe is generated in a single pass using collected answers.
5. Local loopback server is launched from the immutable verified release (`~/.characteros-tools/releases/<key>/`).

```text
USER (Writer)
  │
  │ /characteros or /sua
  ▼
WORKBUDDY (Conversational & Creative Agent)
  │
  ├── 1. Gathers story premise, format, cast size, tone, and genre FIRST
  ├── 2. Resolves remote Git ref (git ls-remote) & verifies runtime integrity
  ├── 3. Mounts verified immutable release (~/.characteros-tools/releases/<key>/)
  ├── 4. Generates complete universe in one pass using collected answers
  └── 5. Submits & persists via localhost API, launching detached host process
  │
  │ HTTP (JSON) on 127.0.0.1:8765
  ▼
LOCAL CHARACTEROS RUNTIME SERVER
  │  ├── Schema validation & deterministic compilers
  │  ├── Workspace persistence (~/.characteros/)
  │  └── Bundled production web assets (web/index.html)
  │
  ▼
BROWSER WORKBENCH (http://127.0.0.1:8765/?workspace=<id>)
```

- **WorkBuddy is the sole agent and creative orchestrator.**
- **The Skill uses Git-based, SHA-256 verified runtime distribution.**
- **CharacterOS is the deterministic workbench and persistent store.**
- **No separate Expert team architecture.**
- **No SaaS or cloud dependency.**

---

## Quick Start

### 1. In WorkBuddy
Install `CharacterOS.zip` into your WorkBuddy skills directory and type:
```text
/characteros A dark psychological-thriller screenplay about five researchers trapped in an Antarctic station.
```
WorkBuddy will generate the entire universe in a single pass, validate it, save it, and provide a direct link to your local browser workbench.

### 2. Standalone CLI & Local Server
Install the runtime wheel:
```bash
pip install dist/story_universe_architect_workbench-1.1.0-py3-none-any.whl
```
Start the local server:
```bash
characteros start
```
Open `http://127.0.0.1:8765` in your browser.

---

## Release Artifacts

The authoritative release process produces exactly two distribution packages under `dist/`:

```text
dist/
├── CharacterOS.zip                                                 # WorkBuddy Skill
└── story_universe_architect_workbench-1.1.0-py3-none-any.whl       # Local CharacterOS Runtime + Web App
```

Run the one-command release packager and test suite:
```bash
python scripts/release.py
```

---

## Documentation

- [System Architecture](docs/ARCHITECTURE.md)
- [Data Contract & Protocol](docs/DATA_CONTRACT.md)
- [WorkBuddy User Guide](docs/WORKBUDDY.md)
- [Release Automation](docs/RELEASE.md)
- [Developer Setup](docs/SETUP.md)
- [Design System](docs/DESIGN.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

---

## License

See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
