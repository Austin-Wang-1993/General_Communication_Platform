import type { LifecyclePhase } from '../types/scenario';

const PHASE_LABEL: Record<LifecyclePhase, string> = {
  draft: '草稿',
  intake_committed: '已提交描述',
  creation_running: '创作进行中',
  creation_failed: '创作失败',
  creation_succeeded: '创作完成',
  runtime_active: '练习中',
};

export function lifecyclePhaseLabel(phase: string): string {
  return PHASE_LABEL[phase as LifecyclePhase] ?? phase;
}

/** P2a：仅创作完成后可进入对话页（前端需求 P2a-02-02） */
export function canEnterChatPhase(phase: string): boolean {
  return phase === 'creation_succeeded' || phase === 'runtime_active';
}
