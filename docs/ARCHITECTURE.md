# CharacterOS — System Architecture

## Mental Model & Topology

CharacterOS is a localhost-first narrative workbench built around a clear separation of concerns:

```text
USER (Writer)
  │
  │ /characteros or /sua
  ▼
WORKBUDDY (Conversational & Creative Agent)
  │
  ▼
CharacterOS Skill
  │
  ├── 1. Detects or acquires local CharacterOS runtime (Mode 1, 2, or 3)
  ├── 2. Starts or reuses the local server on 127.0.0.1:8765
  ├── 3. Collects story requirements conversationally (Premise, Format, Cast Size, Tone, Genre)
  ├── 4. Generates complete universe in a single pass
  ├── 5. Submits and validates universe via localhost REST API
  ├── 6. Persists canonical universe to user workspace
  └── 7. Delivers concise summary + localhost URL to user
  │
  │ localhost HTTP (JSON)
  ▼
CHARACTEROS RUNTIME SERVER (127.0.0.1:<port>)
  │
  ├── Local server (ThreadingHTTPServer)
  ├── Canonical schema & domain model (Draft 2020-12)
  ├── Deterministic compilers (Bible, Seeds, Visual Prompts, SVG Atlas)
  ├── Workspace persistence engine (~/.characteros/)
  ├── Targeted patch updates & proposal acceptance
  └── Bundled production web assets (web/index.html)
          │
          ▼
http://127.0.0.1:<port>/?workspace=<id>
          │
          ▼
FIXED LOCAL CHARACTEROS WEB APPLICATION (Browser Workbench)
```

---

## The Responsibility Boundary

| Responsibility Area | Owned By | Description |
|---|---|---|
| **Conversational Interface** | WorkBuddy | Talks with writer, asks questions, extracts premise. |
| **Creative Reasoning** | WorkBuddy | Cast design, personality, voice samples, asymmetric tension, narrative gap proposals. |
| **Workflow Orchestration** | WorkBuddy | Single-pass generation sequence, repair of validation errors, submission. |
| **Semantic Edits** | WorkBuddy | Interpreting natural-language change requests, updating structured fields. |
| **Canonical Data Model** | CharacterOS Runtime | Universe schema, 16 communication lenses, field limits, typing. |
| **Deterministic Validation** | CharacterOS Runtime | Graph connectivity, endpoint verification, non-empty voice samples. |
| **Persistence & State** | CharacterOS Runtime | Atomic writes to per-user data directory (`~/.characteros/workspaces`). |
| **Deterministic Compilers** | CharacterOS Runtime | Generating prompt kits, story seeds, markdown bible, SVG graph. |
| **Interactive Workbench** | CharacterOS Web UI | Node-dragging SVG relationship atlas, card inspector, proposal accept/reject, manual review, exports. |

---

## Dismantling the Previous Expert Architecture

In previous prototype iterations:
- An independent Expert team existed (`story-universe-architect-team-team-lead`, `story-architect`, `relationship-mapper`).
- The application was coupled to intermediate file polling in `exchange/` directories.
- Authors were forced to manually click approvals in the browser between stages.

In this final locked architecture:
1. **No Independent Expert Nodes**: WorkBuddy is the only AI agent.
2. **No Second Orchestrator in Runtime**: The runtime is deterministic domain code without LLM orchestration.
3. **No Forced Gating in Initial Generation**: The initial universe is created in a single pass.
4. **Post-Generation Human Review**: The writer can review, inspect, and tweak the universe in the web app or continue chatting in WorkBuddy.
5. **No SaaS Dependency**: 100% loopback-bound, zero network leakage.
