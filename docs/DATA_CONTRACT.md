# CharacterOS — Data Contract & Protocol Specification

## REST API Specification

### 1. System Health
`GET /api/health`
- **Response**:
  ```json
  {
    "status": "ok",
    "version": "1.1.0",
    "port": 8765,
    "pid": 24104,
    "workspaces_count": 2,
    "data_dir": "/path/to/.characteros/workspaces"
  }
  ```

### 2. Workspaces
`GET /api/workspaces`
- **Response**: List of workspace summaries with IDs, titles, premise concepts, character counts, and update timestamps.

`POST /api/workspaces`
- **Body**: `{"workspace_id": "slug", "universe": { ... }}`
- **Response**: `201 Created` with saved workspace object.

`GET /api/workspaces/<workspace_id>/universe`
- **Response**: Complete canonical universe JSON.

`PUT /api/workspaces/<workspace_id>/universe`
- **Body**: `{"universe": { ... }}`
- **Response**: `200 OK` with updated universe.

`PATCH /api/workspaces/<workspace_id>/universe`
- **Supported Actions**:
  - `rename_character`: `{"action": "rename_character", "character_id": "...", "name": "..."}`
  - `update_character`: `{"action": "update_character", "character": { ... }}`
  - `update_relationship`: `{"action": "update_relationship", "relationship": { ... }}`
  - `accept_suggestion`: `{"action": "accept_suggestion", "suggestion_id": "..."}`
  - `reject_suggestion`: `{"action": "reject_suggestion", "suggestion_id": "..."}`
  - `update_story`: `{"action": "update_story", "fields": { ... }}`

`DELETE /api/workspaces/<workspace_id>`
- **Response**: `200 OK` `{"ok": true, "deleted": "..."}`

### 3. Dry-Run Validation
`POST /api/validate`
- **Body**: `{"universe": { ... }}`
- **Response**:
  - `200 OK`: `{"ok": true, "errors": [], "warnings": [...]}`
  - `422 Unprocessable Entity`: `{"ok": false, "errors": ["..."], "warnings": []}`

### 4. Exports
`GET /api/workspaces/<workspace_id>/export/<format>`
- Supported formats:
  - `zip`: Returns full portable `.zip` package.
  - `markdown` / `bible`: Returns formatted Character Bible markdown.
  - `prompts`: Returns 4-category visual prompt kit markdown.
  - `seeds`: Returns relationship-driven scene seeds JSON.
  - `svg`: Returns standalone interactive SVG graph.
  - `json`: Returns raw universe JSON.
