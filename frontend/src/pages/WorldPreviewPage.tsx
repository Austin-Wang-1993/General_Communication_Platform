/**
 * P2.5 生成世界预览：按 framework 列出各小节与 narrative 摘要。
 */

import { useMemo } from 'react';
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

function sectionRelPath(ch: number, sec: number): string {
  return `sections/ch${ch}_sec${sec}/narrative.json`;
}

export function WorldPreviewPage() {
  const { scenarioId = '' } = useParams();
  const nav = useNavigate();

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

  const narrQueries = useQueries({
    queries: sectionKeys.map((row) => ({
      queryKey: ['raw-file', scenarioId, row.ch, row.sec, 'narrative'],
      queryFn: () => getRawJsonFile(scenarioId, sectionRelPath(row.ch, row.sec)) as Promise<NarrativeShape>,
      enabled: Boolean(scenarioId) && sectionKeys.length > 0,
      retry: false,
    })),
  });

  const pkg = pkgQ.data;
  const totalSections = sectionKeys.length;
  const doneCount = pkg?.assets.section_assets_count ?? 0;

  return (
    <div className="min-h-screen flex flex-col bg-paper pb-[max(120px,env(safe-area-inset-bottom))]">
      <AppHeader title="生成世界" backTo="/scenarios" />

      <div className="px-3 pt-2 max-w-lg mx-auto w-full">
        <CreationStepper current={3} />
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

        {sectionKeys.map((row, idx) => {
          const q = narrQueries[idx];
          const body = (q?.data as NarrativeShape | undefined)?.section_body;
          const npcs = (q?.data as NarrativeShape | undefined)?.appearing_npc_ids;
          const loading = q?.isLoading;
          const failed = q?.isError;
          return (
            <article key={`${row.ch}-${row.sec}`} className="card space-y-2">
              <h3 className="text-sm font-semibold text-ink">
                第{row.ch}章 {row.chapterTitle} · {row.ch}-{row.sec} {row.title}
              </h3>
              {loading && <p className="text-xs text-ink-soft">读取 narrative…</p>}
              {failed && <p className="text-xs text-ink-soft">本节 narrative 尚未就绪或读取失败。</p>}
              {body && <p className="text-sm text-ink leading-relaxed whitespace-pre-wrap">{body}</p>}
              {npcs && npcs.length > 0 && (
                <p className="text-[11px] text-ink-soft">
                  出现人物（NPC id）：{npcs.join('、')}
                </p>
              )}
            </article>
          );
        })}
      </main>

      <div className="sticky bottom-0 left-0 right-0 p-3 bg-paper/95 backdrop-blur border-t border-border-subtle max-w-lg mx-auto w-full space-y-2">
        <div className="flex gap-2">
          <Link to={`/scenarios/${scenarioId}/framework-preview`} className="btn-secondary flex-1 text-center">
            上一步
          </Link>
          <Link to="/scenarios" className="btn-secondary flex-1 text-center">
            完成并返回列表
          </Link>
        </div>
        <button
          type="button"
          className="btn-primary w-full"
          disabled={!pkg || !canEnterChatPhase(pkg.lifecycle_phase)}
          onClick={() => nav(`/scenarios/${scenarioId}/chat`)}
        >
          直接预览剧情
        </button>
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
