/**
 * P2.1 基本描述：五字段 + commit-intake；成功后进入 P2.2 框架 Job（前端需求 §3.5）。
 */

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { CreationStepper } from '../components/CreationStepper';
import { AppHeader } from '../components/layout/AppHeader';
import { lifecyclePhaseLabel } from '../lib/lifecycle';
import { ApiError } from '../services/apiClient';
import {
  commitIntake,
  getScenarioPackage,
  startFrameworkJob,
} from '../services/scenariosApi';

export function IntakeWizardPage() {
  const { scenarioId = '' } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();

  const pkgQ = useQuery({
    queryKey: ['scenario-package', scenarioId],
    queryFn: () => getScenarioPackage(scenarioId),
    enabled: Boolean(scenarioId),
  });

  const [scenarioTitle, setScenarioTitle] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [sceneBrief, setSceneBrief] = useState('');
  const [goalBrief, setGoalBrief] = useState('');
  const [vocab, setVocab] = useState('');
  const [forceReset, setForceReset] = useState(false);
  const [formErr, setFormErr] = useState<string | null>(null);

  useEffect(() => {
    const t = pkgQ.data?.scenario_title;
    if (t && !scenarioTitle) {
      setScenarioTitle(t);
    }
  }, [pkgQ.data?.scenario_title, scenarioTitle]);

  const valid = useMemo(() => {
    const st = scenarioTitle.trim();
    const dn = displayName.trim();
    const sb = sceneBrief.trim();
    const gb = goalBrief.trim();
    if (st.length < 1 || st.length > 120) return false;
    if (dn.length < 1 || dn.length > 120) return false;
    if (sb.length < 40 || sb.length > 20000) return false;
    if (gb.length < 10 || gb.length > 20000) return false;
    if (vocab.length > 5000) return false;
    return true;
  }, [scenarioTitle, displayName, sceneBrief, goalBrief, vocab]);

  const commitM = useMutation({
    mutationFn: async () => {
      await commitIntake(scenarioId, {
        scenario_title: scenarioTitle.trim(),
        user_display_name: displayName.trim(),
        scene_brief: sceneBrief.trim(),
        user_goal_brief: goalBrief.trim(),
        vocabulary_list: vocab.trim(),
        force_reset_creation: forceReset,
      });
      const job = await startFrameworkJob(scenarioId);
      return job;
    },
    onSuccess: (job) => {
      void qc.invalidateQueries({ queryKey: ['scenario-packages'] });
      void qc.invalidateQueries({ queryKey: ['scenario-package', scenarioId] });
      nav(`/scenarios/${scenarioId}/jobs/${job.job_id}/framework`, { replace: true });
    },
    onError: (e: unknown) => {
      if (e instanceof ApiError && e.errorCode === 'framework_already_exists') {
        setFormErr('检测到已有剧情框架：请勾选「重置创作」后再提交。');
        return;
      }
      setFormErr(errMsg(e));
    },
  });

  if (!scenarioId) {
    return <p className="p-4 text-sm">缺少场景 ID</p>;
  }

  if (pkgQ.isLoading) {
    return (
      <div className="min-h-screen bg-paper p-6">
        <p className="text-sm text-ink-soft">加载场景包…</p>
      </div>
    );
  }

  if (pkgQ.isError) {
    return (
      <div className="min-h-screen bg-paper p-6">
        <p className="text-sm text-danger">无法加载：{errMsg(pkgQ.error)}</p>
        <Link to="/scenarios" className="mt-4 inline-block text-sm text-accent">
          返回清单
        </Link>
      </div>
    );
  }

  const pkg = pkgQ.data!;
  const blocked =
    pkg.lifecycle_phase === 'creation_running' || pkg.lifecycle_phase === 'runtime_active';

  if (blocked) {
    return (
      <div className="min-h-screen flex flex-col bg-paper">
        <AppHeader title="基本描述" backTo="/scenarios" />
        <main className="p-5 max-w-lg mx-auto">
          <div className="card text-sm text-ink-soft">
            当前阶段为「{lifecyclePhaseLabel(pkg.lifecycle_phase)}」，不能在此编辑五字段。
            <div className="mt-4">
              <Link to="/scenarios" className="text-accent font-medium">
                返回语言场景
              </Link>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-paper pb-[max(96px,env(safe-area-inset-bottom))]">
      <AppHeader title="基本描述" backTo="/scenarios" />

      <div className="px-3 pt-3 max-w-lg mx-auto w-full space-y-2">
        <CreationStepper current={1} />
        <div className="flex flex-wrap justify-end gap-x-3 gap-y-1 text-[11px]">
          {pkg.assets.has_story_framework && (
            <Link className="text-accent font-medium" to={`/scenarios/${scenarioId}/framework-preview`}>
              查看框架预览
            </Link>
          )}
          {pkg.assets.section_assets_complete && (
            <Link className="text-accent font-medium" to={`/scenarios/${scenarioId}/world-preview`}>
              查看世界预览
            </Link>
          )}
        </div>
      </div>

      <main className="flex-1 px-3 py-4 space-y-4 max-w-lg mx-auto w-full">
        <p className="text-center text-xs text-ink-soft">给我们做个简单介绍吧</p>

        {pkg.assets.has_story_framework && (
          <label className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-ink">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={forceReset}
              onChange={(e) => setForceReset(e.target.checked)}
            />
            <span>我已修改五字段，并同意<strong>清空</strong>已生成的框架 / 角色 / 小节产物后重新创作（G3）。</span>
          </label>
        )}

        {formErr && (
          <div className="rounded-md bg-red-50 px-3 py-2 text-xs text-danger border border-red-100">
            {formErr}
          </div>
        )}

        <label className="block text-sm">
          <span className="text-ink font-medium">场景名称</span>
          <input
            className="mt-1 w-full rounded-md border border-border-subtle px-3 py-2 text-sm"
            value={scenarioTitle}
            onChange={(e) => setScenarioTitle(e.target.value)}
            maxLength={120}
          />
        </label>

        <label className="block text-sm">
          <span className="text-ink font-medium">你的称呼</span>
          <input
            className="mt-1 w-full rounded-md border border-border-subtle px-3 py-2 text-sm"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            maxLength={120}
          />
        </label>

        <label className="block text-sm">
          <span className="text-ink font-medium">你梦想的场景</span>
          <span className="text-ink-soft text-xs ml-1">（≥40 字）</span>
          <textarea
            className="mt-1 w-full min-h-[120px] rounded-md border border-border-subtle px-3 py-2 text-sm leading-relaxed"
            value={sceneBrief}
            onChange={(e) => setSceneBrief(e.target.value)}
          />
        </label>

        <label className="block text-sm">
          <span className="text-ink font-medium">你的目标</span>
          <span className="text-ink-soft text-xs ml-1">（≥10 字）</span>
          <textarea
            className="mt-1 w-full min-h-[100px] rounded-md border border-border-subtle px-3 py-2 text-sm leading-relaxed"
            value={goalBrief}
            onChange={(e) => setGoalBrief(e.target.value)}
          />
        </label>

        <label className="block text-sm">
          <span className="text-ink font-medium">专业词汇</span>
          <span className="text-ink-soft text-xs ml-1">（可选）</span>
          <textarea
            className="mt-1 w-full min-h-[72px] rounded-md border border-border-subtle px-3 py-2 text-sm"
            value={vocab}
            onChange={(e) => setVocab(e.target.value)}
          />
        </label>
      </main>

      <footer className="fixed bottom-0 left-0 right-0 border-t border-border-subtle bg-paper/95 p-3 pb-[max(12px,env(safe-area-inset-bottom))] backdrop-blur flex gap-2 max-w-lg mx-auto w-full">
        <Link
          to="/scenarios"
          className="flex-1 rounded-md border border-border-subtle py-2.5 text-center text-sm text-ink-soft"
        >
          返回
        </Link>
        <button
          type="button"
          className="btn-primary flex-[2]"
          disabled={!valid || commitM.isPending}
          onClick={() => {
            setFormErr(null);
            commitM.mutate();
          }}
        >
          {commitM.isPending ? '提交中…' : '下一步'}
        </button>
      </footer>
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
