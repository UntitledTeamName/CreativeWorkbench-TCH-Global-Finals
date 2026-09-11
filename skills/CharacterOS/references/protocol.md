# CharacterOS — WorkBuddy Integration Protocol

## Overview

The CharacterOS protocol defines the deterministic contract between **WorkBuddy** (the conversational and creative orchestrator) and the **CharacterOS Runtime** (the localhost persistence, validation, and editing workbench).

```text
WORKBUDDY CHAT / ORCHESTRATION
              │
              │  Localhost HTTP (JSON)
              ▼
   CHARACTEROS RUNTIME SERVER (127.0.0.1:<port>)
              │
              ├─ REST Endpoints (/api/...)
              ├─ Deterministic Validation & Compilers
              ├─ Workspace Persistence (~/.characteros/)
              └─ Bundled Web Application (HTML5 / SVG)
              │
              ▼
    BROWSER WORKBENCH (http://127.0.0.1:<port>/?workspace=<id>)
```

---

## Server Discovery & Lifecycle

### Health Probe
- **Endpoint**: `GET /api/health`
- **Host**: `127.0.0.1:<port>`
- **Response** (`200 OK`):
  ```json
  {
    "status": "ok",
    "version": "1.1.0",
    "port": 8765,
    "pid": 12345,
    "workspaces_count": 3,
    "data_dir": "C:\\Users\\...\\.characteros\\workspaces"
  }
  ```

---

## Workspace Operations

### 1. List Workspaces
- **Endpoint**: `GET /api/workspaces`
- **Response** (`200 OK`):
  ```json
  {
    "workspaces": [
      {
        "id": "antarctic-threshold",
        "title": "The Glass Ice",
        "concept": "...",
        "characters_count": 5,
        "relationships_count": 7,
        "revision": 1,
        "updated_at": "2026-09-11T20:00:00Z"
      }
    ]
  }
  ```

### 2. Retrieve Universe
- **Endpoint**: `GET /api/workspaces/<workspace_id>/universe`
- **Response** (`200 OK`): Canonical Universe JSON object.
- **Errors**:
  - `404 Not Found`: Workspace does not exist.

### 3. Publish Complete Universe
- **Endpoint**: `PUT /api/workspaces/<workspace_id>/universe` (or `POST /api/workspaces`)
- **Headers**: `Content-Type: application/json`
- **Body**: Complete candidate Universe JSON matching `schema/universe.schema.json`.
- **Response** (`200 OK` or `201 Created`):
  ```json
  {
    "workspace_id": "antarctic-threshold",
    "path": "...",
    "updated_at": "...",
    "universe": { ... }
  }
  ```
- **Errors**:
  - `422 Unprocessable Entity`: Validation failure. Body contains exact structural error list.

### 4. Patch Universe (Targeted Natural-Language Updates)
- **Endpoint**: `PATCH /api/workspaces/<workspace_id>/universe`
- **Headers**: `Content-Type: application/json`
- **Supported Patch Actions**:
  - **Rename Character**:
    ```json
    { "action": "rename_character", "character_id": "sarah", "name": "Sarah Vance" }
    ```
  - **Update Character**:
    ```json
    { "action": "update_character", "character": { "id": "sarah", "core_fear": "..." } }
    ```
  - **Update Relationship**:
    ```json
    { "action": "update_relationship", "relationship": { "id": "rel-1", "tension": "..." } }
    ```
  - **Accept Suggestion**:
    ```json
    { "action": "accept_suggestion", "suggestion_id": "prop-1" }
    ```
  - **Reject Suggestion**:
    ```json
    { "action": "reject_suggestion", "suggestion_id": "prop-1" }
    ```
  - **Update Story**:
    ```json
    { "action": "update_story", "fields": { "concept": "...", "tone": "..." } }
    ```
- **Response** (`200 OK`): Updated workspace object.

### 5. Validate Candidate Universe (Dry Run)
- **Endpoint**: `POST /api/validate`
- **Headers**: `Content-Type: application/json`
- **Body**: `{"universe": { ... }}`
- **Response**:
  - `200 OK`: `{"ok": true, "errors": [], "warnings": [...]}`
  - `422 Unprocessable Entity`: `{"ok": false, "errors": ["..."], "warnings": []}`

---

## Workspace URL

WorkBuddy directs the author to the interactive workbench using:

```text
http://127.0.0.1:<port>/?workspace=<workspace_id>
```

When opened, the CharacterOS server dynamically injects the requested workspace's universe into the client HTML, instantly rendering:
- The Character Bible & Cards
- The Interactive SVG Relationship Atlas
- The Narrative Gap Suggestions
- The Compiled Visual Prompt Kit & Story Seeds
- Export options (ZIP, Markdown, SVG, JSON, HTML)
