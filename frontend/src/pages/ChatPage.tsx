/**
 * P3 对话主界面 + P3a 章节进节（与产品主链路一致的首版可用 UI）。
 */

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';

import { ChapterSectionPickerModal } from '../components/chat/ChapterSectionPickerModal';
import { AppHeader } from '../components/layout/AppHeader';
import { ApiError } from '../services/apiClient';
import { getRawJsonFile } from '../services/debugAssetsApi';
import { enterSection, getRuntime, postUserTurn } from '../services/runtimeApi';

type RuntimeShape = {
  scenario_id?: string;
  lifecycle_phase?: string;
  current_chapter_id?: number | null;
  current_section_id?: number | null;
  runtime_awaiting_user?: boolean;
  section_narrative?: { appearing_npc_ids?: string[]; section_body?: string };
  character_roster?: { characters?: Array<{ character_id: string; name: string }> };
  turns?: TurnRow[];
};

type TurnRow = {
  turn_id?: string;
  speaker_id?: string;
  recipient_id?: string;
  content?: string;
  expects_user_response?: boolean;
  turn_writer?: string;
};

type FrameworkChapter = {
  chapter_id: number;
  chapter_title: string;
  sections: Array<{ section_id: number; section_title: string }>;
};

export function ChatPage() {
  const { scenarioId = '' } = useParams();
  const qc = useQueryClient();
  const [input, setInput] = useState('');
  const [recipientOpen, setRecipientOpen] = useState(false);
  const [chapterOpen, setChapterOpen] = useState(false);
  const [recipientId, setRecipientId] = useState('');

  const rtQ = useQuery({
    queryKey: ['runtime', scenarioId],
    queryFn: () => getRuntime(scenarioId) as Promise<RuntimeShape>,
    enabled: Boolean(scenarioId),
    retry: false,
  });

  const fwQ = useQuery({
    queryKey: ['raw-file', scenarioId, 'framework-chat-picker'],
    queryFn: async () => {
      const raw = (await getRawJsonFile(scenarioId, 'framework.json')) as {
        story_framework?: { chapters?: FrameworkChapter[] };
      };
      return raw?.story_framework?.chapters ?? [];
    },
    enabled: Boolean(scenarioId),
    retry: false,
  });

  const rt = rtQ.data;
  const ch = rt?.current_chapter_id ?? 1;
  const sec = rt?.current_section_id ?? 1;
  const turns = rt?.turns ?? [];
  const appearing = rt?.section_narrative?.appearing_npc_ids ?? [];

  const nameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of rt?.character_roster?.characters ?? []) {
      m.set(c.character_id, c.name);
    }
    m.set('user', '你');
    return m;
  }, [rt?.character_roster?.characters]);

  useEffect(() => {
    if (!appearing.length) {
      return;
    }
    if (!recipientId || !appearing.includes(recipientId)) {
      setRecipientId(appearing[0]!);
    }
  }, [appearing, recipientId]);

  const enterM = useMutation({
    mutationFn: ({ c, s }: { c: number; s: number }) => enterSection(scenarioId, c, s),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['runtime', scenarioId] });
      setChapterOpen(false);
    },
  });

  const sendM = useMutation({
    mutationFn: () =>
      postUserTurn(scenarioId, ch, sec, {
        content: input.trim(),
        recipient_id: recipientId,
      }),
    onSuccess: () => {
      setInput('');
      void qc.invalidateQueries({ queryKey: ['runtime', scenarioId] });
    },
  });

  const lifecycleErr =
    rtQ.error instanceof ApiError && rtQ.error.errorCode === 'lifecycle_phase_invalid'
      ? rtQ.error.message
      : null;
  const pointerHint =
    rtQ.error instanceof ApiError &&
    rtQ.error.details &&
    typeof rtQ.error.details === 'object' &&
    'hint' in (rtQ.error.details as object)
      ? String((rtQ.error.details as { hint?: string }).hint ?? '')
      : '';

  return (
    <div className="min-h-screen flex flex-col bg-paper">
      <AppHeader title="对话练习" backTo="/scenarios" end={
        <button type="button" className="text-xs text-accent font-medium shrink-0" onClick={() => setChapterOpen(true)}>
          章节
        </button>
      } />

      <main className="flex-1 overflow-y-auto px-3 py-3 space-y-3 max-w-lg mx-auto w-full pb-40">
        {rtQ.isLoading && <p className="text-sm text-ink-soft text-center">加载运行态…</p>}

        {rtQ.isError && (
          <div className="card space-y-3 text-sm">
            <p className="text-danger">无法加载对话：{errMsg(rtQ.error)}</p>
            {(lifecycleErr || pointerHint) && (
              <p className="text-xs text-ink-soft leading-relaxed">
                {pointerHint || '若创作已完成，请选择一节进入以开始对话。'}
              </p>
            )}
            <button
              type="button"
              className="btn-primary w-full"
              disabled={enterM.isPending}
              onClick={() => enterM.mutate({ c: 1, s: 1 })}
            >
              {enterM.isPending ? '进节中…' : '尝试进入 第1章第1节'}
            </button>
            <button type="button" className="btn-secondary w-full" onClick={() => setChapterOpen(true)}>
              章节列表…
            </button>
          </div>
        )}

        {rt && (
          <>
            <div className="rounded-lg border border-border-subtle bg-white/80 px-3 py-2 text-[11px] text-ink-soft space-y-0.5">
              <div>
                指针：{rt.current_chapter_id} / {rt.current_section_id} · 等待你回复：
                <span className="text-ink font-medium">{String(rt.runtime_awaiting_user)}</span>
              </div>
              {rt.section_narrative?.section_body && (
                <p className="text-ink leading-snug pt-1 line-clamp-4">{rt.section_narrative.section_body}</p>
              )}
            </div>

            <div className="space-y-2">
              {turns.map((t, i) => {
                const isUser = t.speaker_id === 'user';
                return (
                  <div key={t.turn_id || i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={[
                        'max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-relaxed shadow-sm',
                        isUser ? 'bg-emerald-600 text-white rounded-br-md' : 'bg-amber-100 text-ink rounded-bl-md',
                      ].join(' ')}
                    >
                      {!isUser && (
                        <p className="text-[10px] opacity-80 mb-1">
                          {nameById.get(t.speaker_id || '') || t.speaker_id}
                        </p>
                      )}
                      <p className="whitespace-pre-wrap">{t.content}</p>
                    </div>
                  </div>
                );
              })}
              {sendM.isPending && (
                <div className="flex justify-start">
                  <div className="rounded-2xl bg-amber-50 border border-amber-100 px-3 py-2 text-xs text-ink-soft">
                    NPC 正在回复…
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </main>

      <div className="fixed bottom-0 left-0 right-0 border-t border-border-subtle bg-paper/95 backdrop-blur px-3 py-2 pb-[max(12px,env(safe-area-inset-bottom))] max-w-lg mx-auto w-full space-y-2">
        <div className="flex gap-2">
          <button type="button" className="btn-secondary flex-1 text-xs" onClick={() => setRecipientOpen(true)}>
            选择对象
          </button>
          <button type="button" className="btn-secondary flex-1 text-xs" onClick={() => setChapterOpen(true)}>
            章节列表
          </button>
        </div>
        <div className="flex gap-2 items-end">
          <textarea
            className="flex-1 min-h-[44px] max-h-28 rounded-lg border border-border-subtle px-3 py-2 text-sm resize-none"
            rows={2}
            placeholder={rt?.runtime_awaiting_user ? '输入英文…' : '当前等待 NPC，暂不可输入'}
            value={input}
            disabled={!rt?.runtime_awaiting_user || sendM.isPending}
            onChange={(e) => setInput(e.target.value)}
          />
          <button
            type="button"
            className="btn-primary shrink-0 self-stretch px-4"
            disabled={!rt?.runtime_awaiting_user || !input.trim() || sendM.isPending}
            onClick={() => sendM.mutate()}
          >
            发送
          </button>
        </div>
        {sendM.isError && (
          <p className="text-[11px] text-danger text-center">{errMsg(sendM.error)}</p>
        )}
      </div>

      {recipientOpen && (
        <div className="fixed inset-0 z-40 bg-black/40 flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-paper w-full max-w-lg rounded-t-2xl sm:rounded-2xl p-4 shadow-xl space-y-3">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-semibold">选择说话对象（recipient）</h3>
              <button type="button" className="text-xs text-ink-soft" onClick={() => setRecipientOpen(false)}>
                关闭
              </button>
            </div>
            <p className="text-[11px] text-ink-soft">须为本节 narrative 中的 NPC（appearing_npc_ids）。</p>
            <ul className="space-y-2 max-h-60 overflow-y-auto">
              {appearing.map((id) => (
                <li key={id}>
                  <label className="flex items-center gap-2 cursor-pointer rounded-lg border border-border-subtle px-3 py-2 has-[:checked]:border-accent">
                    <input
                      type="radio"
                      name="rcp"
                      checked={recipientId === id}
                      onChange={() => setRecipientId(id)}
                    />
                    <span className="text-sm">
                      {nameById.get(id) || id} <span className="text-ink-soft text-xs">({id})</span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
            {appearing.length === 0 && <p className="text-xs text-ink-soft">暂无 NPC 列表，请先成功进入一节。</p>}
            <button type="button" className="btn-primary w-full" onClick={() => setRecipientOpen(false)}>
              确定
            </button>
          </div>
        </div>
      )}

      <ChapterSectionPickerModal
        open={chapterOpen}
        onClose={() => setChapterOpen(false)}
        chapters={fwQ.data ?? []}
        initialChapterId={ch}
        initialSectionId={sec}
        busy={enterM.isPending}
        onConfirm={(c, s) => enterM.mutate({ c, s })}
      />
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
