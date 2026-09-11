# Story Universe Architect — System Architecture

## Mental Model & Topology

Story Universe Architect (SUA) is a localhost-first narrative workbench built around a clear separation of concerns:

```text
USER (Writer)
  │
  │ /sua
  ▼
WORKBUDDY (Conversational & Creative Agent)
  │
  ▼
StoryUniverseArchitect Skill
  │
  ├── 1. Detects or acquires local SUA runtime (Mode 1, 2, or 3)
  ├── 2. Starts or reuses the local server on 127.0.0.1:8765
  ├── 3. Collects story requirements conversationally (Premise, Format, Cast Size, Tone, Genre)
  ├── 4. Generates complete universe in a single pass
  ├── 5. Submits and validates universe via localhost REST API
  ├── 6. Persists canonical universe to user workspace
  └── 7. Delivers concise summary + localhost URL to user
  │
  │ localhost HTTP (JSON)
  ▼
SUA RUNTIME SERVER (127.0.0.1:<port>)
  │
  ├── Local server (ThreadingHTTPServer)
  ├── Canonical schema & domain model (Draft 2020-12)
  ├── Deterministic compilers (Bible, Seeds, Visual Prompts, SVG Atlas)
  ├── Workspace persistence engine (~/.story-universe-architect/)
  ├── Targeted patch updates & proposal acceptance
  └── Bundled production web assets (web/index.html)
          │
          ▼
http://127.0.0.1:<port>/?workspace=<id>
          │
          ▼
FIXED LOCAL SUA WEB APPLICATION (Browser Workbench)
```

---

## The Responsibility Boundary

| Responsibility Area | Owned By | Description |
|---|---|---|
| **Conversational Interface** | WorkBuddy | Talks with writer, asks questions, extracts premise. |
| **Creative Reasoning** | WorkBuddy | Cast design, personality, voice samples, asymmetric tension, narrative gap proposals. |
| **Workflow Orchestration** | WorkBuddy | Single-pass generation sequence, repair of validation errors, submission. |
| **Semantic Edits** | WorkBuddy | Interpreting natural-language change requests, updating structured fields. |
| **Canonical Data Model** | SUA Runtime | Universe schema, 16 communication lenses, field limits, typing. |
| **Deterministic Validation** | SUA Runtime | Graph connectivity, endpoint verification, non-empty voice samples. |
| **Persistence & State** | SUA Runtime | Atomic writes to per-user data directory (`~/.story-universe-architect/workspaces`). |
| **Deterministic Compilers** | SUA Runtime | Generating prompt kits, story seeds, markdown bible, SVG graph. |
| **Interactive Workbench** | SUA Runtime Web UI | Node-dragging SVG relationship atlas, card inspector, proposal accept/reject, manual review, exports. |

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
