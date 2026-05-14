You output ONLY valid JSON (no markdown). The root object MUST match:

{
  "scenario_id": "<uuid>",
  "chapter_id": <int>,
  "section_id": <int>,
  "section_objective": "<English 40-1200 chars>"
}

`section_objective` must be an observable English task for the learner, consistent with `section_narrative.section_body` and `enriched_user_goal`.

Forbidden keys anywhere: candidate_outcomes, outcome_id, outcome_type, branch_id, probability, score, turn_writer.

User JSON contains: scenario_id, chapter_id, section_id, framework_section, section_narrative (object), character_roster, enriched_user_goal.
