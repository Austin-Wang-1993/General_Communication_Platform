You output ONLY valid JSON (no markdown, no code fences). The root object MUST be **flat** with **exactly** these keys:

`scenario_id`, `chapter_id`, `section_id`, `section_objective`

{
  "scenario_id": "<uuid from user JSON>",
  "chapter_id": <int from user JSON>,
  "section_id": <int from user JSON>,
  "section_objective": "<English 40-1200 chars>"
}

Do **not** nest under `section_mission` or any wrapper.

`section_objective` must be an observable English task for the learner, consistent with `section_narrative.section_body` and `enriched_user_goal`.

Forbidden keys anywhere: candidate_outcomes, outcome_id, outcome_type, branch_id, probability, score, turn_writer.

User JSON contains: scenario_id, chapter_id, section_id, framework_section, section_narrative (object), character_roster, enriched_user_goal.
