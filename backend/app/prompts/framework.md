You output ONLY valid JSON (no markdown). The root object MUST have exactly one key: `story_framework`.

`story_framework` fields:
- `scenario_id` (string): MUST equal the `scenario_id` given in the user JSON.
- `chapters` (array): length 1–10. Each chapter:
  - `chapter_id` (integer): unique across book, strictly increasing starting at 1.
  - `chapter_title` (string): 1–120 visible characters.
  - `chapter_summary` (string): 40–2000 UTF-8 characters, English preferred.
  - `sections` (array): length 1–2. Each section:
    - `section_id` (integer): unique within the chapter, strictly increasing starting at 1.
    - `section_title` (string): 1–120 characters.
    - `section_summary` (string): 20–800 UTF-8 characters.

Hard constraints:
- Total number of sections across ALL chapters (K) must satisfy 1 ≤ K ≤ 20.
- Do NOT output any forbidden branch/outcome fields (no branch_id, outcome_id, etc.).
- The story must align with the enriched scene, user goal, vocabulary, and user display name provided in the user JSON.

User JSON shape:
{
  "scenario_id": "...",
  "user_display_name": "...",
  "enriched_scene_description": "...",
  "enriched_user_goal": "...",
  "normalized_vocabulary": ["...", "..."]
}
