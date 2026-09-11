# CharacterOS

**CharacterOS** is an offline-first, localhost-first creative writing workbench and narrative compiler. Part of [CharacterOS: Creative Workbench for Workbuddy](https://github.com/UntitledTeamName/CharacterOS). It transforms a single premise into a fully connected, structurally sound story universe with cast profiles, asymmetric relationship maps, narrative gap additions, a 4-category visual prompt kit, and directional story seeds.

---

## Final Architecture Overview

```text
USER (Writer)
  │
  │ /characteros or /sua
  ▼
WORKBUDDY (Conversational & Creative Agent)
  │
  ▼
CharacterOS Skill
  │  ├── Detects / acquires runtime (Modes 1, 2, 3)
  │  ├── Starts / reuses local server
  │  ├── Collects requirements conversationally
  │  ├── Generates complete universe in one pass
  │  └── Submits & persists via localhost API
  │
  │ HTTP (JSON) on 127.0.0.1:8765
  ▼
LOCAL CHARACTEROS RUNTIME SERVER
  │  ├── Schema validation & deterministic compilers
  │  ├── Workspace persistence (~/.characteros/)
  │  └── Bundled production web assets
  │
  ▼
BROWSER WORKBENCH (http://127.0.0.1:8765/?workspace=<id>)
```

- **WorkBuddy is the sole agent and creative orchestrator.**
- **The Skill is the integration contract.**
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
