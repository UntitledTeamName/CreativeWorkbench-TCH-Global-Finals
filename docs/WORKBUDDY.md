# CharacterOS — WorkBuddy User Guide

## Getting Started in WorkBuddy

CharacterOS is designed for seamless, agentic operation inside WorkBuddy.

### Invocation
Type `/characteros` (or `/sua`) in your WorkBuddy chat:

```text
User:
/characteros
```

WorkBuddy will automatically:
1. Detect or acquire the local CharacterOS runtime.
2. Verify server health.
3. Prompt you conversationally for your story requirements:
   - Premise / Concept
   - Format (e.g. Screenplay, Novel outline)
   - Cast size (4–6 characters)
   - Genre and Tone

### Natural Intake
You can provide everything in one go:

```text
User:
/characteros A dark psychological-thriller screenplay about five researchers
trapped in an Antarctic station after discovering that one person's
memories have been fabricated.
```

WorkBuddy detects the format, cast size, tone, and genre automatically and proceeds without redundant questioning.

---

## Single-Pass Generation

WorkBuddy orchestrates generation of the entire story universe in **one autonomous pass**:
1. Creates the cast with 16 narrative communication lenses, voices, and psychological baselines.
2. Builds the connected, asymmetric relationship network with dual perspectives and breaking points.
3. Proposes 2–3 optional narrative gap additions.
4. Compiles the 4-category visual prompt kit and relationship-driven story seeds.
5. Validates against the CharacterOS schema and persists to your local workspace.

You receive a concise chat summary and a localhost link:
```text
http://127.0.0.1:8765/?workspace=antarctic-station
```

---

## Conversational Editing

After generation, you can continue chatting in WorkBuddy to refine your world:

```text
User:
Make Sarah distrust Marcus more, but don't change their shared history.
```

WorkBuddy retrieves the workspace, updates the tension and read while preserving protected history, validates the update, and saves it back to the CharacterOS workspace.

---

## Local Workbench

Opening the URL in your browser gives you the full interactive workbench:
- Drag-and-drop relationship atlas nodes.
- Inspect dual interpretations on each edge.
- Accept or reject optional character proposals.
- Edit character profiles and voice samples manually.
- Export to complete Story ZIP, Markdown Bible, or Vector SVG.
