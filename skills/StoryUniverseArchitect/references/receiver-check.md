# Story Universe Architect — Receiver Self-Check

Before submitting candidate story universe data to the local SUA workbench, verify every check:

## 1. Top-Level Universe Check
- [ ] `schema_version` is `"1.0"`.
- [ ] `id` is a valid kebab-case slug (`^[a-z][a-z0-9_-]+$`).
- [ ] `concept` preserves the writer's premise.
- [ ] `revision` is an integer (1 for initial creation, previous + 1 for updates).
- [ ] `visual` contains all 5 required fields: `palette` (array of 4–6 colors), `lighting`, `texture`, `composition`, `style`.

## 2. Character Cast Check
- [ ] Exactly 4 to 6 initial characters in `characters`.
- [ ] Character IDs are unique and lowercase kebab-case.
- [ ] Every `archetype_id` exists in `references/archetypes.json` (e.g. `architect`, `catalyst`, `mediator`, `skeptic`, etc.).
- [ ] Every character has 2–6 concrete `tendencies`.
- [ ] Every character has 3–5 dialogue lines in `voice_samples`.
- [ ] `core_desire` and `core_fear` are present and distinct.

## 3. Relationship Graph Check
- [ ] At least `max(3, len(characters) - 1)` relationships.
- [ ] All `source` and `target` IDs exist in `characters`.
- [ ] No self-loops (`source != target`).
- [ ] Exactly one relationship per character pair.
- [ ] Every character is connected (graph is fully connected).
- [ ] Each edge has distinct `source_read` and `target_read` representing contrasting interpretations of `shared_history`.
- [ ] `intensity` is an integer between 1 and 5 inclusive.

## 4. Suggestions Check
- [ ] Exactly 2 or 3 suggestions in `suggestions`.
- [ ] All suggestions have `"status": "pending"`.
- [ ] Suggested characters do NOT appear in `characters` canon.
- [ ] Proposed edges only connect the suggested character to existing canon characters.

## 5. Provenance Check
- [ ] `provenance` is present with `mode`: `"workbuddy"`.
