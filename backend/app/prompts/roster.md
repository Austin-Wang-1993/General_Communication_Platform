You output ONLY valid JSON (no markdown). The root object MUST have exactly one key: `character_roster`.

`character_roster` fields:
- `scenario_id` (string): MUST equal the scenario_id in the user JSON.
- `characters` (array): length 2–6 (one user + 1–5 NPCs).
  Each element:
  - `character_id` (string): machine id; for the human learner MUST be exactly `user`.
  - `name` (string): display name, 1–120 chars.
  - `role` (string): job title / social role, 4–200 chars English.
  - `personality` (string): observable traits for dialogue style, 20–800 chars English.
  - `is_user` (boolean): exactly ONE entry must be true and that entry MUST have `character_id` == `user`.

NPC rules:
- Every NPC must be a plausible human colleague in the story world implied by `story_framework`.
- Each NPC `character_id` must be unique, lowercase snake_case English token without spaces (examples: `lead_pm`, `engineer_alex`).

User JSON contains:
- `scenario_id`
- `user_display_name`
- `enriched_scene_description`
- `enriched_user_goal`
- `normalized_vocabulary` (array of strings)
- `story_framework` (object): the already-approved framework; roster must be consistent with chapter/section roles.
