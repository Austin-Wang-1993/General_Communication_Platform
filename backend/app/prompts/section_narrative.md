You output ONLY valid JSON (no markdown). The root object MUST match this shape exactly:

{
  "scenario_id": "<uuid>",
  "chapter_id": <int>,
  "section_id": <int>,
  "section_body": "<English narrative 300-20000 chars>",
  "appearing_npc_ids": ["<npc_character_id>", "..."]
}

Rules:
- `appearing_npc_ids` length MUST be 1 or 2; NEVER include `"user"`.
- Each id MUST appear as an NPC `character_id` in the provided `character_roster`.
- `section_body` must align with `framework_section`, `enriched_scene_description`, `normalized_vocabulary`, and roster personalities.

User JSON contains: scenario_id, chapter_id, section_id, framework_section (object), character_roster (object), enriched_scene_description, enriched_user_goal, normalized_vocabulary (array).
