# Story Universe Architect — Troubleshooting Guide

## Common Issues & Diagnoses

### Port 8765 Already In Use
- **Behavior**: The server automatically probes ports `8765-8770`. If `8765` is occupied by another application, SUA binds to the first free port in the range.
- **Resolution**: Check active port via `sua status` or `python -m story_universe_architect.cli status`.

### Stale Server Process
- **Behavior**: A previously spawned background server remains running.
- **Resolution**:
  ```bash
  sua stop
  ```
  Or kill the PID recorded in `~/.story-universe-architect/sua.pid`.

### Wheel Integrity Check Failed (Mode 3)
- **Behavior**: Automatic GitHub download reports `Runtime integrity check failed`.
- **Cause**: Corrupted download or mismatched `references/installation.json` hash.
- **Resolution**: Clear `~/.story-universe-architect/releases/` and re-acquire, or install wheel manually with `pip install`.

### Validation Errors On Submission
- **Behavior**: WorkBuddy receives `HTTP 422 Unprocessable Entity`.
- **Cause**: Candidate universe does not satisfy schema requirements (e.g. fewer than 4 characters, disconnected graph, self-loop relationship).
- **Resolution**: Review error details returned by `/api/validate` or check `references/receiver-check.md`.
