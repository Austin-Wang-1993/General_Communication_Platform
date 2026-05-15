/**
 * 与后端 `snake_case` 对齐的场景包类型（API 文档 §2）。
 */

export type LifecyclePhase =
  | 'draft'
  | 'intake_committed'
  | 'creation_running'
  | 'creation_failed'
  | 'creation_succeeded'
  | 'runtime_active';

export interface PackageSummary {
  scenario_id: string;
  scenario_title: string;
  lifecycle_phase: LifecyclePhase;
  current_chapter_id: number | null;
  current_section_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface PackageDetail {
  scenario_id: string;
  scenario_title: string;
  lifecycle_phase: LifecyclePhase;
  current_chapter_id: number | null;
  current_section_id: number | null;
  runtime_awaiting_user: boolean | null;
  created_at: string;
  updated_at: string;
  assets: {
    has_intake_snapshot: boolean;
    has_scenario_analysis: boolean;
    has_story_framework: boolean;
    has_character_roster: boolean;
    section_assets_count: number;
    section_assets_complete: boolean;
  };
}

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled';

export interface JobStatusResponse {
  job_id: string;
  type: 'framework' | 'world';
  scenario_id: string;
  status: JobStatus;
  current_step_label: string;
  progress_hint: string | null;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
  error_code: string | null;
  error_message: string | null;
}
