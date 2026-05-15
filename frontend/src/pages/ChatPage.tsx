/**
 * P3 对话主界面：顶栏工具条（前端需求 §3.10 **F-P3-00**、F-P3-01～05）+ P3a 进节 + R1/R2 弹窗。
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';

import { ChapterSectionPickerModal } from '../components/chat/ChapterSectionPickerModal';
import { AppHeader } from '../components/layout/AppHeader';
import { ApiError } from '../services/apiClient';
import { getRawJsonFile } from '../services/debugAssetsApi';
import { postHint, postSectionAnalytics, getSectionAnalyticsLatest } from '../services/r1r2Api';
import { enterSection, getRuntime, postUserTurn } from '../services/runtimeApi';

type RuntimeShape = {
  scenario_id?: string;
  lifecycle_phase?: string;
  current_chapter_id?: number | null;
  current_section_id?: number | null;
  runtime_awaiting_user?: boolean;
  section_narrative?: {
    appearing_npc_ids?: string[];
    section_body?: string;
    chapter_id?: number;
    section_id?: number;
  };
  section_mission?: { section_objective?: string; chapter_id?: number; section_id?: number };
  character_roster?: { characters?: Array<{ character_id: string; name: string; role?: string }> };
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

type HintShape = {
  linked_turn_id?: string;
  hint_status?: string;
  analysis_markdown?: string;
  suggested_utterances?: string[];
  generated_at?: string;
};

type AnalyticsShape = {
  evaluated_through_turn_id?: string;
  section_analytics_status?: string;
  holistic_feedback_markdown?: string;
  generated_at?: string;
};

export function ChatPage() {
  const { scenarioId = '' } = useParams();
  const qc = useQueryClient();
  const [input, setInput] = useState('');
  const [recipientOpen, setRecipientOpen] = useState(false);
  const [chapterOpen, setChapterOpen] = useState(false);
  const [recipientId, setRecipientId] = useState('');

  const [bgOpen, setBgOpen] = useState(false);
  const [hintOpen, setHintOpen] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);
  const [hintBody, setHintBody] = useState<HintShape | null>(null);
  const [hintErr, setHintErr] = useState<string | null>(null);

  const [analyticsOpen, setAnalyticsOpen] = useState(false);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsErr, setAnalyticsErr] = useState<string | null>(null);
  const [analyticsView, setAnalyticsView] = useState<AnalyticsShape | null>(null);
  const [lastGoodAnalytics, setLastGoodAnalytics] = useState<AnalyticsShape | null>(null);

  const [toast, setToast] = useState<string | null>(null);
  const didAttemptAutoEnter = useRef(false);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 3200);
  }, []);

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

  useEffect(() => {
    setLastGoodAnalytics(null);
  }, [ch, sec, scenarioId]);

  const nameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of rt?.character_roster?.characters ?? []) {
      m.set(c.character_id, c.name);
    }
    m.set('user', '你');
    return m;
  }, [rt?.character_roster?.characters]);

  const targetTurnIdForHint = useMemo(() => lastNpcAwaitingUserTurnId(turns), [turns]);

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
      setInput('');
      void qc.invalidateQueries({ queryKey: ['runtime', scenarioId] });
      setChapterOpen(false);
    },
  });

  useEffect(() => {
    didAttemptAutoEnter.current = false;
    enterM.reset();
    // 仅切换场景包时重置；不把 enterM 放入依赖以免引用抖动导致反复清空
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional
  }, [scenarioId]);

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

  const pointerUnset =
    rtQ.isError && rtQ.error && isRuntimePointerUnsetError(rtQ.error);
  const suppressRuntimeErrorCard = Boolean(pointerUnset && !enterM.isError);

  useEffect(() => {
    if (!scenarioId) return;
    if (!pointerUnset || didAttemptAutoEnter.current) return;
    if (fwQ.isLoading) return;
    didAttemptAutoEnter.current = true;
    const ids = fwQ.isError ? { c: 1, s: 1 } : firstSectionS0(fwQ.data);
    enterM.mutate(ids);
  }, [scenarioId, pointerUnset, fwQ.isLoading, fwQ.isError, fwQ.data, enterM]);

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

  const hintAllowed = Boolean(rt?.runtime_awaiting_user && targetTurnIdForHint);

  async function openHintFlow() {
    if (!rt) return;
    if (!rt.runtime_awaiting_user) {
      showToast('当前无需回复建议');
      return;
    }
    const tid = targetTurnIdForHint;
    if (!tid) {
      showToast('未找到可对齐的 NPC 提问回合');
      return;
    }
    setHintOpen(true);
    setHintErr(null);
    setHintLoading(true);
    setHintBody(null);
    try {
      const res = (await postHint(scenarioId, ch, sec, { target_turn_id: tid })) as HintShape;
      setHintBody(res);
    } catch (e: unknown) {
      setHintErr(errMsg(e));
    } finally {
      setHintLoading(false);
    }
  }

  async function openAnalyticsFlow() {
    if (!rt) return;
    if (turns.length === 0) {
      showToast('本节暂无可分析对话');
      return;
    }
    setAnalyticsOpen(true);
    setAnalyticsErr(null);
    setAnalyticsLoading(true);
    setAnalyticsView(null);
    try {
      const prev = (await getSectionAnalyticsLatest(scenarioId, ch, sec)) as AnalyticsShape | undefined;
      if (prev && prev.section_analytics_status === 'ready' && prev.holistic_feedback_markdown) {
        setLastGoodAnalytics(prev);
      }
      const res = (await postSectionAnalytics(scenarioId, ch, sec)) as AnalyticsShape;
      setAnalyticsView(res);
      if (res.section_analytics_status === 'ready' && res.holistic_feedback_markdown) {
        setLastGoodAnalytics(res);
      } else if (res.section_analytics_status === 'failed') {
        setAnalyticsErr('本次生成失败，已保留上一份成功内容（若有）。');
      }
    } catch (e: unknown) {
      setAnalyticsErr(errMsg(e));
    } finally {
      setAnalyticsLoading(false);
    }
  }

  const toolbar = rt || suppressRuntimeErrorCard ? (
    <div className="flex gap-1 overflow-x-auto pb-0.5 max-w-lg mx-auto w-full [-webkit-overflow-scrolling:touch]">
      <Link
        to="/scenarios"
        className="shrink-0 rounded-md border border-border-subtle bg-white px-2.5 py-1.5 text-xs font-medium text-ink hover:border-accent"
        onClick={() => setInput('')}
      >
        返回首页
      </Link>
      {rt && (
        <>
          <button type="button" className="shrink-0 btn-secondary text-xs py-1.5 px-2" onClick={() => setBgOpen(true)}>
            背景介绍
          </button>
          <button
            type="button"
            className="shrink-0 btn-secondary text-xs py-1.5 px-2 disabled:opacity-40"
            disabled={!hintAllowed}
            onClick={() => void openHintFlow()}
          >
            回答提示
          </button>
          <button type="button" className="shrink-0 btn-secondary text-xs py-1.5 px-2" onClick={() => void openAnalyticsFlow()}>
            总结分析
          </button>
          <button type="button" className="shrink-0 btn-secondary text-xs py-1.5 px-2" onClick={() => setChapterOpen(true)}>
            查看列表
          </button>
        </>
      )}
      {!rt && suppressRuntimeErrorCard && (
        <button
          type="button"
          className="shrink-0 btn-secondary text-xs py-1.5 px-2 disabled:opacity-40"
          disabled={fwQ.isLoading || enterM.isPending}
          onClick={() => setChapterOpen(true)}
        >
          查看列表
        </button>
      )}
    </div>
  ) : null;

  return (
    <div className="min-h-screen flex flex-col bg-paper">
      <AppHeader title="对话练习" below={toolbar} />

      {toast && (
        <div className="mx-3 mt-2 rounded-md bg-ink px-3 py-2 text-xs text-white shadow-md z-50">{toast}</div>
      )}

      <main className="flex-1 overflow-y-auto px-3 py-3 space-y-3 max-w-lg mx-auto w-full pb-44">
        {rtQ.isLoading && !suppressRuntimeErrorCard && (
          <p className="text-sm text-ink-soft text-center">加载运行态…</p>
        )}

        {suppressRuntimeErrorCard && (
          <div className="card space-y-2 text-sm text-ink">
            <p className="text-ink font-medium">正在为你准备对话</p>
            <p className="text-xs text-ink-soft leading-relaxed">
              {fwQ.isLoading && '正在读取章节结构…'}
              {!fwQ.isLoading && enterM.isPending && '正在进入全书第一个练习小节，并触发 NPC 开场…'}
              {!fwQ.isLoading && !enterM.isPending && enterM.isSuccess && !rt && '正在加载会话…'}
              {!fwQ.isLoading && !enterM.isPending && !enterM.isSuccess && !enterM.isError && '正在初始化…'}
            </p>
          </div>
        )}

        {rtQ.isError && !suppressRuntimeErrorCard && (
          <div className="card space-y-3 text-sm">
            <p className="text-danger">无法加载对话：{errMsg(rtQ.error)}</p>
            {enterM.isError && <p className="text-danger text-xs">进节失败：{errMsg(enterM.error)}</p>}
            {(lifecycleErr || pointerHint) && (
              <p className="text-xs text-ink-soft leading-relaxed">
                {pointerHint || '若创作已完成，请选择一节进入以开始对话。'}
              </p>
            )}
            <button
              type="button"
              className="btn-primary w-full"
              disabled={enterM.isPending}
              onClick={() => enterM.mutate(firstSectionS0(fwQ.data))}
            >
              {enterM.isPending ? '进节中…' : '重试进入首个小节'}
            </button>
            <button type="button" className="btn-secondary w-full" onClick={() => setChapterOpen(true)}>
              查看列表…
            </button>
          </div>
        )}

        {rt && (
          <>
            <div className="rounded-lg border border-border-subtle bg-white/80 px-3 py-2 text-[11px] text-ink-soft space-y-0.5">
              <div>
                第{ch}章第{sec}节 · 等待你回复：
                <span className="text-ink font-medium">{String(rt.runtime_awaiting_user)}</span>
              </div>
            </div>

            <div className="space-y-2">
              {turns.map((t, i) => {
                const isUser = t.speaker_id === 'user';
                const speakerLabel = nameById.get(t.speaker_id || '') || t.speaker_id || '…';
                const recipientLabel = nameById.get(t.recipient_id || '') || t.recipient_id || '…';
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
                          {speakerLabel}
                        </p>
                      )}
                      {isUser && (
                        <p className="text-[10px] text-emerald-100/90 mb-1 text-right">
                          {speakerLabel} → {recipientLabel}
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
        <button type="button" className="btn-secondary w-full text-xs" onClick={() => setRecipientOpen(true)}>
          选择信息接收人
        </button>
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
        {sendM.isError && <p className="text-[11px] text-danger text-center">{errMsg(sendM.error)}</p>}
      </div>

      {/* 背景介绍 */}
      {bgOpen && rt && (
        <ModalShell title="背景介绍" onClose={() => setBgOpen(false)}>
          <div className="space-y-3 text-sm text-ink">
            <section>
              <h4 className="text-xs font-semibold text-ink-soft uppercase tracking-wide">本节叙事</h4>
              <p className="mt-1 whitespace-pre-wrap leading-relaxed">{rt.section_narrative?.section_body ?? '—'}</p>
            </section>
            <section>
              <h4 className="text-xs font-semibold text-ink-soft uppercase tracking-wide">目标任务</h4>
              <p className="mt-1 whitespace-pre-wrap leading-relaxed">{rt.section_mission?.section_objective ?? '—'}</p>
            </section>
            <section>
              <h4 className="text-xs font-semibold text-ink-soft uppercase tracking-wide">出场角色</h4>
              <ul className="mt-1 space-y-2">
                {(rt.section_narrative?.appearing_npc_ids ?? []).map((id) => {
                  const chInfo = rt.character_roster?.characters?.find((c) => c.character_id === id);
                  return (
                    <li key={id} className="rounded-md border border-border-subtle bg-white px-3 py-2 text-xs">
                      <span className="font-medium">{chInfo?.name ?? id}</span>
                      <span className="text-ink-soft font-mono ml-1">({id})</span>
                      {chInfo?.role && <p className="text-ink-soft mt-0.5">{chInfo.role}</p>}
                    </li>
                  );
                })}
              </ul>
              {(rt.section_narrative?.appearing_npc_ids ?? []).length === 0 && <p className="text-xs text-ink-soft">—</p>}
            </section>
          </div>
        </ModalShell>
      )}

      {/* 回答提示 R1 */}
      {hintOpen && (
        <ModalShell title="回答提示" onClose={() => setHintOpen(false)}>
          {hintLoading && <p className="text-sm text-ink-soft">生成中，请稍候…</p>}
          {hintErr && <p className="text-sm text-danger">{hintErr}</p>}
          {hintBody && (
            <div className="space-y-3 text-sm">
              {hintBody.hint_status === 'stale' && (
                <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-md px-2 py-1">
                  该提示已过期，请关闭后重试「回答提示」。
                </p>
              )}
              {hintBody.hint_status === 'failed' && (
                <p className="text-sm text-danger whitespace-pre-wrap">{hintBody.analysis_markdown || '生成失败'}</p>
              )}
              {hintBody.hint_status === 'ready' && (
                <>
                  <div className="whitespace-pre-wrap text-ink leading-relaxed border border-border-subtle rounded-lg p-3 bg-white text-sm">
                    {hintBody.analysis_markdown}
                  </div>
                  {hintBody.suggested_utterances && hintBody.suggested_utterances.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-ink-soft mb-2">可参考英文表达</h4>
                      <ul className="space-y-2">
                        {hintBody.suggested_utterances.map((u, idx) => (
                          <li key={idx} className="rounded-md bg-emerald-50 border border-emerald-100 px-3 py-2 text-xs text-ink">
                            {u}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
              {hintBody.generated_at && (
                <p className="text-[10px] text-ink-soft font-mono">生成时间：{hintBody.generated_at}</p>
              )}
            </div>
          )}
        </ModalShell>
      )}

      {/* 总结分析 R2 */}
      {analyticsOpen && (
        <ModalShell title="总结分析" onClose={() => setAnalyticsOpen(false)}>
          {analyticsLoading && <p className="text-sm text-ink-soft">正在生成中，请稍后</p>}
          {analyticsErr && <p className="text-sm text-danger">{analyticsErr}</p>}
          {analyticsView?.section_analytics_status === 'ready' && analyticsView.holistic_feedback_markdown && (
            <div className="whitespace-pre-wrap text-ink leading-relaxed border border-border-subtle rounded-lg p-3 bg-white text-sm">
              {analyticsView.holistic_feedback_markdown}
            </div>
          )}
          {analyticsView?.section_analytics_status === 'failed' && lastGoodAnalytics?.holistic_feedback_markdown && (
            <div className="mt-3 space-y-1">
              <p className="text-xs text-ink-soft">上一份成功复盘：</p>
              <div className="whitespace-pre-wrap text-ink leading-relaxed border border-border-subtle rounded-lg p-3 bg-white text-sm">
                {lastGoodAnalytics.holistic_feedback_markdown}
              </div>
            </div>
          )}
          {!analyticsLoading &&
            analyticsErr &&
            !analyticsView &&
            lastGoodAnalytics?.holistic_feedback_markdown && (
              <div className="mt-2 whitespace-pre-wrap text-ink leading-relaxed border border-border-subtle rounded-lg p-3 bg-white text-sm">
                {lastGoodAnalytics.holistic_feedback_markdown}
              </div>
            )}
          {analyticsView?.generated_at && (
            <p className="text-[10px] text-ink-soft font-mono mt-2">生成时间：{analyticsView.generated_at}</p>
          )}
        </ModalShell>
      )}

      {recipientOpen && (
        <div className="fixed inset-0 z-40 bg-black/40 flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-paper w-full max-w-lg rounded-t-2xl sm:rounded-2xl p-4 shadow-xl space-y-3">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-semibold">选择信息接收人</h3>
              <button type="button" className="text-xs text-ink-soft" onClick={() => setRecipientOpen(false)}>
                关闭
              </button>
            </div>
            <p className="text-[11px] text-ink-soft">候选范围：本节 appearing_npc_ids（不含 user）。</p>
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

function lastNpcAwaitingUserTurnId(turns: TurnRow[]): string | null {
  for (let i = turns.length - 1; i >= 0; i--) {
    const t = turns[i]!;
    if (t.speaker_id && t.speaker_id !== 'user' && t.expects_user_response && t.turn_id) {
      return t.turn_id;
    }
  }
  return null;
}

function ModalShell(props: { title: string; children: ReactNode; onClose: () => void }) {
  const { title, children, onClose } = props;
  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/45 p-0 sm:p-4"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        className="bg-paper w-full max-w-lg max-h-[85vh] rounded-t-2xl sm:rounded-2xl shadow-xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center px-4 py-3 border-b border-border-subtle shrink-0">
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          <button type="button" className="text-xs text-ink-soft px-2 py-1" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="px-4 py-3 overflow-y-auto text-left">{children}</div>
      </div>
    </div>
  );
}

function isRuntimePointerUnsetError(err: unknown): boolean {
  return (
    err instanceof ApiError &&
    err.errorCode === 'lifecycle_phase_invalid' &&
    err.message.includes('运行指针未设置')
  );
}

/** 全书叙事顺序首小节 S[0]：framework 第一章第一节；缺省回退 1-1 */
function firstSectionS0(chapters: FrameworkChapter[] | undefined): { c: number; s: number } {
  const ch0 = chapters?.[0];
  const s0 = ch0?.sections?.[0];
  if (ch0 && s0) {
    return { c: ch0.chapter_id, s: s0.section_id };
  }
  return { c: 1, s: 1 };
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
