/**
 * P2.2 / P2.4：创作 Job 轮询页（G10 进度文案 + 取消）。
 * 成功后自动跳转：framework → P2.3 框架预览；world → P2.5 世界预览。
 */

import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';

import { AppHeader } from '../components/layout/AppHeader';
import { ApiError } from '../services/apiClient';
import { cancelJob, getJob } from '../services/scenariosApi';
import type { JobStatus } from '../types/scenario';

export function JobWaitPage() {
  const { scenarioId = '', jobId = '', jobKind = '' } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();

  const kind = jobKind === 'framework' || jobKind === 'world' ? jobKind : null;

  const jobQ = useQuery({
    queryKey: ['job', scenarioId, jobId],
    queryFn: () => getJob(scenarioId, jobId),
    enabled: Boolean(scenarioId && jobId && kind),
    refetchInterval: (q) => {
      const s = q.state.data?.status as JobStatus | undefined;
      if (!s || s === 'succeeded' || s === 'failed' || s === 'canceled') {
        return false;
      }
      return 1000;
    },
  });

  const cancelM = useMutation({
    mutationFn: () => cancelJob(scenarioId, jobId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scenario-packages'] });
      void qc.invalidateQueries({ queryKey: ['scenario-package', scenarioId] });
      nav('/scenarios', { replace: true });
    },
  });

  const job = jobQ.data;

  useEffect(() => {
    if (!job || !kind || !scenarioId) {
      return;
    }
    if (job.status !== 'succeeded') {
      return;
    }
    if (kind === 'framework') {
      nav(`/scenarios/${scenarioId}/framework-preview`, { replace: true });
    } else {
      nav(`/scenarios/${scenarioId}/world-preview`, { replace: true });
    }
  }, [job?.status, kind, scenarioId, nav, job]);

  if (!kind) {
    return (
      <div className="p-6 text-sm text-danger">
        无效的 Job 类型路径（应为 framework 或 world）。
      </div>
    );
  }

  const terminal = job?.status === 'succeeded' || job?.status === 'failed' || job?.status === 'canceled';

  const title = kind === 'framework' ? '场景框架渲染中' : '专属世界渲染中';

  return (
    <div className="min-h-screen flex flex-col bg-paper">
      <AppHeader title={title} backTo="/scenarios" />

      <main className="flex-1 flex flex-col items-center justify-center px-5 max-w-lg mx-auto w-full">
        {jobQ.isLoading && <p className="text-sm text-ink-soft">读取任务状态…</p>}
        {jobQ.isError && <p className="text-sm text-danger">加载失败：{errMsg(jobQ.error)}</p>}
        {job && (
          <div className="card w-full text-center space-y-3">
            <div className="text-4xl animate-pulse" aria-hidden>
              ✶
            </div>
            <p className="text-sm font-medium text-ink leading-snug">
              {job.current_step_label ||
                (kind === 'framework' ? '正在生成场景框架，请稍候' : '正在生成各小节内容，请稍候')}
            </p>
            {job.progress_hint && <p className="text-xs text-ink-soft font-mono">{job.progress_hint}</p>}
            <p className="text-[11px] text-ink-soft">状态：{job.status}</p>

            {job.status === 'failed' && (
              <p className="text-xs text-danger break-words">{job.error_message || job.error_code || '任务失败'}</p>
            )}

            {!terminal && (
              <button
                type="button"
                className="btn-danger w-full"
                disabled={cancelM.isPending}
                onClick={() => cancelM.mutate()}
              >
                {cancelM.isPending ? '取消中…' : '取消'}
              </button>
            )}

            {job.status === 'succeeded' && (
              <p className="text-xs text-ink-soft">正在进入预览页…</p>
            )}

            {terminal && job.status !== 'succeeded' && (
              <button type="button" className="btn-primary w-full" onClick={() => nav('/scenarios')}>
                返回语言场景
              </button>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

function errMsg(e: unknown): string {
  if (e instanceof ApiError) {
    return `${e.errorCode}：${e.message}`;
  }
  if (e instanceof Error) {
    return e.message;
  }
  return String(e);
}
