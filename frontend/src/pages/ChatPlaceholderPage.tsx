/**
 * P3 首版占位：拉取运行态、支持首次 POST enter 1/1 与展示最近回合。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';

import { AppHeader } from '../components/layout/AppHeader';
import { ApiError } from '../services/apiClient';
import { enterSection, getRuntime } from '../services/runtimeApi';

type RuntimeShape = {
  scenario_id?: string;
  lifecycle_phase?: string;
  current_chapter_id?: number | null;
  current_section_id?: number | null;
  runtime_awaiting_user?: boolean;
  turns?: Array<{
    turn_id?: string;
    speaker_id?: string;
    recipient_id?: string;
    content?: string;
    expects_user_response?: boolean;
  }>;
};

export function ChatPlaceholderPage() {
  const { scenarioId = '' } = useParams();
  const qc = useQueryClient();

  const rtQ = useQuery({
    queryKey: ['runtime', scenarioId],
    queryFn: () => getRuntime(scenarioId) as Promise<RuntimeShape>,
    enabled: Boolean(scenarioId),
    retry: false,
  });

  const enterM = useMutation({
    mutationFn: () => enterSection(scenarioId, 1, 1),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['runtime', scenarioId] });
    },
  });

  const data = rtQ.data;
  const turns = data?.turns ?? [];

  return (
    <div className="min-h-screen flex flex-col bg-paper">
      <AppHeader title="对话练习" backTo="/scenarios" />

      <main className="flex-1 px-3 py-4 space-y-4 max-w-lg mx-auto w-full pb-24">
        <p className="text-xs text-ink-soft">
          P3 完整聊天 UI 开发中。本页可查看运行态 JSON 并尝试首次进节（1-1）。
        </p>

        {rtQ.isLoading && <p className="text-sm text-ink-soft">加载运行态…</p>}

        {rtQ.isError && (
          <div className="card space-y-3">
            <p className="text-sm text-danger">GET runtime 失败：{errMsg(rtQ.error)}</p>
            <button
              type="button"
              className="btn-primary w-full"
              disabled={enterM.isPending}
              onClick={() => enterM.mutate()}
            >
              {enterM.isPending ? '进节中…' : '尝试进入第 1 章第 1 节（自动开场）'}
            </button>
          </div>
        )}

        {data && (
          <div className="space-y-3">
            <div className="card text-xs text-ink-soft space-y-1">
              <div>lifecycle：{data.lifecycle_phase}</div>
              <div>
                指针：{String(data.current_chapter_id)} / {String(data.current_section_id)}
              </div>
              <div>等待用户：{String(data.runtime_awaiting_user)}</div>
            </div>

            <h2 className="text-sm font-semibold text-ink">本节对话</h2>
            <ul className="space-y-2">
              {turns.map((t, i) => (
                <li key={t.turn_id || i} className="rounded-lg border border-border-subtle bg-white p-3 text-sm">
                  <div className="text-[11px] text-ink-soft font-mono">
                    {t.speaker_id} → {t.recipient_id}
                  </div>
                  <p className="mt-1 text-ink leading-relaxed whitespace-pre-wrap">{t.content}</p>
                </li>
              ))}
            </ul>
            {turns.length === 0 && <p className="text-xs text-ink-soft">暂无回合。</p>}
          </div>
        )}

        <Link to="/debug/" className="inline-block text-xs text-accent">
          打开后端调试页（全量接口）
        </Link>
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
