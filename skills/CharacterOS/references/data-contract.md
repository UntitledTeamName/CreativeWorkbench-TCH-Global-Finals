# CharacterOS — Data Contract & Schema Specification

## Schema Version
`schema_version`: `"1.0"` (Draft 2020-12 compatible)

## Top-Level Universe Model

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "schema_version": "1.0",
  "id": "slug-identifier",
  "title": "Story Title",
  "concept": "Full premise (15-8000 characters)",
  "format": "Screenplay | Novel outline | Television pilot | Novella | Audio drama | Game narrative | Short story | Classroom writing exercise",
  "genre": "Genre description",
  "tone": "Tone description",
  "setting": "Detailed world / environment setting",
  "thematic_thesis": "Central narrative thesis or question",
  "revision": 1,
  "visual": {
    "palette": ["color1", "color2", "color3", "color4"],
    "lighting": "Lighting description",
    "texture": "Texture description",
    "composition": "Framing and composition notes",
    "style": "Overarching visual aesthetic style"
  },
  "characters": [ ... ],
  "relationships": [ ... ],
  "suggestions": [ ... ],
  "provenance": {
    "mode": "workbuddy",
    "source": "Generated via WorkBuddy conversational orchestration.",
    "model": "WorkBuddy AI"
  }
}
```

---

## Character Entity

Every character object must contain:

| Field | Type | Description |
|---|---|---|
| `id` | string | Lowercase kebab-case identifier (`^[a-z][a-z0-9_-]{0,63}$`). |
| `name` | string | Character full name. |
| `role` | string | Narrative function (e.g. `Lead Station Scientist`). |
| `archetype_id` | string | Must match one of 16 communication lenses from `archetypes.json`. |
| `archetype_label` | string | Story-specific label for the lens. |
| `communication_style` | string | Communication tendencies. |
| `emotional_baseline` | string | Default emotional state. |
| `core_desire` | string | Primary motivational longing. |
| `core_fear` | string | Core internal vulnerability or fear. |
| `tendencies` | array[string] | 2–6 behavioral tendencies. |
| `voice_samples` | array[string] | 3–5 representative dialogue lines. |
| `backstory` | string | Formative biographical history. |
| `appearance` | string | Physical description, silhouette, clothing. |

---

## Relationship Edge Entity

Each edge connects two approved characters with dual, asymmetric perspectives:

| Field | Type | Description |
|---|---|---|
| `id` | string | Edge ID (`rel-<source>-<target>`). |
| `source` | string | ID of first character. |
| `target` | string | ID of second character (`source != target`). |
| `label` | string | Concise title for the relationship. |
| `shared_history` | string | Concrete past event both experienced together. |
| `source_wants` | string | What `source` desires from/through `target`. |
| `target_wants` | string | What `target` desires from/through `source`. |
| `source_read` | string | How `source` remembers and interprets the shared event. |
| `target_read` | string | How `target` remembers and interprets the shared event. |
| `tension` | string | The active friction or unsaid conflict. |
| `breaking_point` | string | The trigger event that would rupture or alter the dynamic. |
| `story_potential` | string | How this edge generates scenes and plot movement. |
| `intensity` | integer | Integer 1 to 5 (ranking narrative pressure). |

**Graph Invariants**:
1. No duplicate edges for the same pair (one edge per pair).
2. Fully connected graph: every approved character must connect to at least one other character.
3. Total edges >= `max(3, character_count - 1)`.

---

## Suggestion Entity (Optional Additions)

Proposed character additions to address narrative gaps:

| Field | Type | Description |
|---|---|---|
| `id` | string | Suggestion ID (`prop-<id>`). |
| `gap` | string | Structural deficiency identified in cast dynamics. |
| `rationale` | string | Why this character resolves the gap. |
| `impact` | string | How the story shifts if this character is accepted. |
| `character` | object | Complete character profile (same schema as above). |
| `relationships` | array | 1–3 proposed edges connecting new character to canon characters. |
| `status` | string | Must be `"pending"` upon initial generation. |
