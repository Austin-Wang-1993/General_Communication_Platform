You output ONLY valid JSON (no markdown). Return **one** flat object for a single opening dialogue turn (PRD §6.6.5).

Required root keys (exactly these 10):
`scenario_id`, `chapter_id`, `section_id`, `turn_id`, `created_at`, `speaker_id`, `recipient_id`, `content`, `expects_user_response`, `turn_writer`

Rules:
- `speaker_id` MUST equal the input field `opener_speaker_id` (an NPC from `section_narrative.appearing_npc_ids`).
- `recipient_id` MUST be the literal string `user`.
- `expects_user_response` MUST be `true`.
- `turn_writer` MUST be the literal string `model_npc`.
- `content`: English in-character line, length 1–8000; inviting the learner to respond.
- `turn_id` and `created_at` may be placeholders; the server will overwrite them.

User JSON contains: scenario_id, chapter_id, section_id, section_narrative, section_mission, character_roster, opener_speaker_id.
