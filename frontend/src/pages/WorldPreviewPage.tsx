/**
 * P2.5 生成世界预览：按 framework 列出各小节；展开后展示 narrative 正文、mission 目标、出场人物（roster 字段直出）。
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { CreationStepper } from '../components/CreationStepper';
import { AppHeader } from '../components/layout/AppHeader';
import { canEnterChatPhase } from '../lib/lifecycle';
import { ApiError } from '../services/apiClient';
import { getRawJsonFile } from '../services/debugAssetsApi';
import { getScenarioPackage } from '../services/scenariosApi';

type FrameworkShape = {
  story_framework?: {
    chapters?: Array<{
      chapter_id: number;
      chapter_title: string;
      sections: Array<{ section_id: number; section_title: string }>;
    }>;
  };
};

type NarrativeShape = {
  section_body?: string;
  appearing_npc_ids?: string[];
};

type MissionShape = {
  section_objective?: string;
};

type RosterShape = {
  character_roster?: {
    characters?: Array<{
      character_id: string;
      name: string;
      role: string;
      personality?: string;
    }>;
  };
};

function sectionRelPath(ch: number, sec: number): string {
  return `sections/ch${ch}_sec${sec}/narrative.json`;
}

function missionRelPath(ch: number, sec: number): string {
  return `sections/ch${ch}_sec${sec}/mission.json`;
}

function sectionKey(ch: number, sec: number): string {
  return `${ch}-${sec}`;
}

export function WorldPreviewPage() {
  const { scenarioId = '' } = useParams();
  const nav = useNavigate();
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const didInitExpand = useRef(false);

  const pkgQ = useQuery({
    queryKey: ['scenario-package', scenarioId],
    queryFn: () => getScenarioPackage(scenarioId),
    enabled: Boolean(scenarioId),
  });

  const fwQ = useQuery({
    queryKey: ['raw-file', scenarioId, 'framework.json'],
    queryFn: () => getRawJsonFile(scenarioId, 'framework.json') as Promise<FrameworkShape>,
    enabled: Boolean(scenarioId) && Boolean(pkgQ.data?.assets.has_story_framework),
    retry: false,
  });

  const rosterQ = useQuery({
    queryKey: ['raw-file', scenarioId, 'roster.json'],
    queryFn: () => getRawJsonFile(scenarioId, 'roster.json') as Promise<RosterShape>,
    enabled: Boolean(scenarioId) && Boolean(pkgQ.data?.assets.has_character_roster),
    retry: false,
  });

  const sectionKeys = useMemo(() => {
    const chs = fwQ.data?.story_framework?.chapters ?? [];
    const out: Array<{ ch: number; sec: number; title: string; chapterTitle: string }> = [];
    for (const ch of chs) {
      for (const sec of ch.sections ?? []) {
        out.push({
          ch: ch.chapter_id,
          sec: sec.section_id,
          title: sec.section_title,
          chapterTitle: ch.chapter_title,
        });
      }
    }
    return out;
  }, [fwQ.data]);

  useEffect(() => {
    didInitExpand.current = false;
    setExpandedKey(null);
  }, [scenarioId]);

  useEffect(() => {
    if (sectionKeys.length > 0 && !didInitExpand.current) {
      const first = sectionKeys[0];
      setExpandedKey(sectionKey(first.ch, first.sec));
      didInitExpand.current = true;
    }
  }, [sectionKeys]);

  const assetQueries = useQueries({
    queries: sectionKeys.flatMap((row) => [
      {
        queryKey: ['raw-file', scenarioId, row.ch, row.sec, 'narrative'],
        queryFn: () => getRawJsonFile(scenarioId, sectionRelPath(row.ch, row.sec)) as Promise<NarrativeShape>,
        enabled: Boolean(scenarioId) && sectionKeys.length > 0,
        retry: false,
      },
      {
        queryKey: ['raw-file', scenarioId, row.ch, row.sec, 'mission'],
        queryFn: () => getRawJsonFile(scenarioId, missionRelPath(row.ch, row.sec)) as Promise<MissionShape>,
        enabled: Boolean(scenarioId) && sectionKeys.length > 0,
        retry: false,
      },
    ]),
  });

  const npcById = useMemo(() => {
    const m = new Map<string, { name: string; role: string; personality: string }>();
    for (const c of rosterQ.data?.character_roster?.characters ?? []) {
      m.set(c.character_id, {
        name: c.name,
        role: c.role,
        personality: (c.personality ?? '').trim(),
      });
    }
    return m;
  }, [rosterQ.data]);

  const pkg = pkgQ.data;
  const totalSections = sectionKeys.length;
  const doneCount = pkg?.assets.section_assets_count ?? 0;

  return (
    <div className="min-h-screen flex flex-col bg-paper pb-[max(96px,env(safe-area-inset-bottom))]">
      <AppHeader title="生成世界" backTo="/scenarios" backLabel="返回首页" />

      <div className="px-3 pt-2 max-w-lg mx-auto w-full">
        <CreationStepper current={3} />
        <p className="text-center text-sm text-ink-soft -mt-1 pb-2">准备探索你自己的语言王国吧</p>
      </div>

      <main className="flex-1 px-3 py-4 space-y-4 max-w-lg mx-auto w-full">
        {pkgQ.isLoading && <p className="text-sm text-ink-soft">加载中…</p>}
        {pkgQ.isError && <p className="text-sm text-danger">{errMsg(pkgQ.error)}</p>}

        {pkg && (
          <div className="card text-xs text-ink-soft space-y-1">
            <p>
              小节资产进度：<span className="font-mono text-ink">{doneCount}</span> /{' '}
              <span className="font-mono text-ink">{totalSections || '—'}</span>
            </p>
            <p>创作阶段：{pkg.lifecycle_phase}</p>
            {pkg.assets.section_assets_complete ? (
              <p className="text-accent font-medium">全部小节已生成，可进入对话练习。</p>
            ) : (
              <p>若世界任务仍在进行，请返回任务页等待；完成后刷新本页。</p>
            )}
          </div>
        )}

        {fwQ.isError && <p className="text-sm text-danger">无法读取 framework：{errMsg(fwQ.error)}</p>}
        {rosterQ.isError && (
          <p className="text-sm text-danger">无法读取 roster：{errMsg(rosterQ.error)}（出场人物将仅显示 id）</p>
        )}

        {sectionKeys.map((row, idx) => {
          const base = idx * 2;
          const narrQ = assetQueries[base];
          const missQ = assetQueries[base + 1];
          const narr = narrQ?.data as NarrativeShape | undefined;
          const objective = (missQ?.data as MissionShape | undefined)?.section_objective;
          const npcIds = narr?.appearing_npc_ids ?? [];
          const k = sectionKey(row.ch, row.sec);
          const expanded = expandedKey === k;
          const narrLoading = narrQ?.isLoading || missQ?.isLoading;
          return (
            <article key={k} className="card space-y-2">
              <button
                type="button"
                onClick={() => setExpandedKey(expanded ? null : k)}
                className="flex w-full items-start justify-between gap-2 text-left"
              >
                <h3 className="text-sm font-semibold text-ink leading-snug">
                  第{row.ch}章 {row.chapterTitle} · {row.ch}-{row.sec} {row.title}
                </h3>
                <span className="shrink-0 text-ink-soft text-xs pt-0.5" aria-hidden>
                  {expanded ? '▼' : '▶'}
                </span>
              </button>

              {expanded && (
                <div className="space-y-3 border-l-2 border-border-subtle pl-3 ml-0.5">
                  {narrLoading && <p className="text-xs text-ink-soft">读取本节 narrative / mission…</p>}
                  {!narrLoading && (narrQ?.isError || missQ?.isError) && (
                    <p className="text-xs text-amber-800">部分文件读取失败，以下为已成功加载的字段。</p>
                  )}

                  <div className="rounded-lg border border-border-subtle bg-white/70 p-3 space-y-1.5">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-soft">内容描述</p>
                    {narr?.section_body ? (
                      <p className="text-sm text-ink leading-relaxed whitespace-pre-wrap">{narr.section_body}</p>
                    ) : (
                      !narrLoading && <p className="text-xs text-ink-soft">暂无正文。</p>
                    )}
                  </div>

                  <div className="rounded-lg border border-border-subtle bg-white/70 p-3 space-y-1.5">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-soft">小节目标</p>
                    {objective ? (
                      <p className="text-sm text-ink leading-relaxed whitespace-pre-wrap">{objective}</p>
                    ) : (
                      !narrLoading && <p className="text-xs text-ink-soft">暂无目标描述。</p>
                    )}
                  </div>

                  <div className="rounded-lg border border-border-subtle bg-white/70 p-3 space-y-2">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-soft">出场人物</p>
                    {narrLoading ? (
                      <p className="text-xs text-ink-soft">加载出场人物…</p>
                    ) : npcIds.length === 0 ? (
                      <p className="text-xs text-ink-soft">暂无出场 NPC 列表。</p>
                    ) : (
                      <ul className="space-y-3">
                        {npcIds.map((id) => {
                          const c = npcById.get(id);
                          return (
                            <li key={id} className="text-sm border-b border-border-subtle/80 pb-3 last:border-0 last:pb-0">
                              <p>
                                <span className="text-ink-soft text-xs">姓名</span>{' '}
                                <span className="text-ink font-medium">{c?.name ?? id}</span>
                              </p>
                              <p className="mt-1">
                                <span className="text-ink-soft text-xs">角色</span>{' '}
                                <span className="text-ink">{c?.role ?? '—'}</span>
                              </p>
                              <p className="mt-1">
                                <span className="text-ink-soft text-xs">性格与形象</span>{' '}
                                <span className="text-ink leading-relaxed whitespace-pre-wrap">
                                  {c?.personality ? c.personality : '—'}
                                </span>
                              </p>
                              {!c && (
                                <p className="mt-1 text-[11px] font-mono text-ink-soft">character_id：{id}</p>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </main>

      <div className="sticky bottom-0 left-0 right-0 p-3 bg-paper/95 backdrop-blur border-t border-border-subtle max-w-lg mx-auto w-full">
        <div className="flex gap-2">
          <Link to="/scenarios" className="btn-secondary flex-1 text-center">
            返回首页
          </Link>
          <button
            type="button"
            className="btn-primary flex-1"
            disabled={!pkg || !canEnterChatPhase(pkg.lifecycle_phase)}
            onClick={() => nav(`/scenarios/${scenarioId}/chat`)}
          >
            直接开启对话
          </button>
        </div>
      </div>
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
