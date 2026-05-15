/**
 * P2.3 框架预览：剧情概览 + 角色清单（GET raw framework / roster）。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { CreationStepper } from '../components/CreationStepper';
import { AppHeader } from '../components/layout/AppHeader';
import { ApiError } from '../services/apiClient';
import { getRawJsonFile } from '../services/debugAssetsApi';
import { getScenarioPackage, startWorldJob } from '../services/scenariosApi';

type FrameworkShape = {
  story_framework?: {
    chapters?: Array<{
      chapter_id: number;
      chapter_title: string;
      chapter_summary: string;
      sections: Array<{ section_id: number; section_title: string; section_summary: string }>;
    }>;
  };
};

type RosterShape = {
  character_roster?: {
    characters?: Array<{
      character_id: string;
      name: string;
      role: string;
      personality: string;
      is_user: boolean;
    }>;
  };
};

export function FrameworkPreviewPage() {
  const { scenarioId = '' } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();

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

  const worldM = useMutation({
    mutationFn: () => startWorldJob(scenarioId),
    onSuccess: (job) => {
      void qc.invalidateQueries({ queryKey: ['scenario-packages'] });
      nav(`/scenarios/${scenarioId}/jobs/${job.job_id}/world`, { replace: true });
    },
  });

  const pkg = pkgQ.data;
  const fw = fwQ.data;
  const roster = rosterQ.data;
  const chapters = fw?.story_framework?.chapters ?? [];
  const characters = roster?.character_roster?.characters ?? [];

  return (
    <div className="min-h-screen flex flex-col bg-paper pb-[max(96px,env(safe-area-inset-bottom))]">
      <AppHeader title="框架预览" backTo={`/scenarios/${scenarioId}/setup`} />

      <div className="px-3 pt-2 max-w-lg mx-auto w-full">
        <CreationStepper current={2} />
      </div>

      <main className="flex-1 px-3 py-4 space-y-4 max-w-lg mx-auto w-full">
        {pkgQ.isLoading && <p className="text-sm text-ink-soft">加载场景包…</p>}
        {worldM.isError && (
          <div className="rounded-md bg-red-50 px-3 py-2 text-xs text-danger border border-red-100">{errMsg(worldM.error)}</div>
        )}
        {pkgQ.isError && <p className="text-sm text-danger">场景包加载失败：{errMsg(pkgQ.error)}</p>}

        {pkg && !pkg.assets.has_story_framework && (
          <div className="card text-sm text-ink-soft space-y-3">
            <p>尚未生成剧情框架。请先完成「基本描述」并等待框架任务完成。</p>
            <Link to={`/scenarios/${scenarioId}/setup`} className="text-accent font-medium">
              返回基本描述
            </Link>
          </div>
        )}

        {pkg?.assets.has_story_framework && fwQ.isLoading && <p className="text-sm text-ink-soft">加载 framework.json…</p>}
        {fwQ.isError && (
          <p className="text-sm text-danger">无法读取框架文件：{errMsg(fwQ.error)}</p>
        )}

        {chapters.length > 0 && (
          <section className="card space-y-3">
            <h2 className="text-sm font-semibold text-ink">剧情概览</h2>
            <ul className="space-y-3 text-sm text-ink leading-relaxed">
              {chapters.map((ch) => (
                <li key={ch.chapter_id} className="border-b border-border-subtle last:border-0 pb-3 last:pb-0">
                  <p className="font-medium">
                    第{ch.chapter_id}章 {ch.chapter_title}
                  </p>
                  <p className="mt-1 text-ink-soft text-xs leading-snug">{ch.chapter_summary}</p>
                  <ul className="mt-2 space-y-2 text-xs">
                    {ch.sections.map((s) => (
                      <li key={s.section_id} className="pl-2 border-l-2 border-accent/40">
                        <span className="font-medium text-ink">
                          {ch.chapter_id}-{s.section_id} {s.section_title}
                        </span>
                        <p className="text-ink-soft mt-0.5">{s.section_summary}</p>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </section>
        )}

        {pkg?.assets.has_character_roster && rosterQ.isLoading && (
          <p className="text-sm text-ink-soft">加载 roster.json…</p>
        )}
        {rosterQ.isError && <p className="text-xs text-danger">角色清单读取失败：{errMsg(rosterQ.error)}</p>}

        {characters.length > 0 && (
          <section className="card space-y-3">
            <h2 className="text-sm font-semibold text-ink">角色人物清单</h2>
            <ul className="space-y-3">
              {characters.map((c) => (
                <li key={c.character_id} className="rounded-lg border border-border-subtle bg-white p-3 text-sm">
                  <div className="flex justify-between gap-2">
                    <span className="font-medium text-ink">{c.name}</span>
                    {c.is_user && <span className="text-[10px] text-accent shrink-0">你</span>}
                  </div>
                  <p className="text-xs text-ink-soft mt-1">{c.role}</p>
                  <p className="text-xs text-ink mt-1 leading-snug">{c.personality}</p>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>

      <div className="sticky bottom-0 left-0 right-0 p-3 bg-paper/95 backdrop-blur border-t border-border-subtle max-w-lg mx-auto w-full flex gap-2">
        <Link to={`/scenarios/${scenarioId}/setup`} className="btn-secondary flex-1 text-center">
          上一步
        </Link>
        <button
          type="button"
          className="btn-primary flex-1"
          disabled={!pkg?.assets.has_story_framework || worldM.isPending}
          onClick={() => worldM.mutate()}
        >
          {worldM.isPending ? '启动中…' : '下一步：生成专属世界'}
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
