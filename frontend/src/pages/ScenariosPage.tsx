/**
 * P2 语言场景清单 + P2a 浮层 + P2b 删除确认（前端需求文档 §3.2~§3.4）。
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

import { AppHeader } from '../components/layout/AppHeader';
import { canEnterChatPhase, lifecyclePhaseLabel } from '../lib/lifecycle';
import {
  createScenarioPackage,
  deleteScenarioPackage,
  listScenarioPackages,
} from '../services/scenariosApi';
import type { PackageSummary } from '../types/scenario';
import { ApiError } from '../services/apiClient';

export function ScenariosPage() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [sheet, setSheet] = useState<PackageSummary | null>(null);
  const [confirmDel, setConfirmDel] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const listQ = useQuery({
    queryKey: ['scenario-packages'],
    queryFn: listScenarioPackages,
  });

  const createM = useMutation({
    mutationFn: () => createScenarioPackage({}),
    onSuccess: (res) => {
      void qc.invalidateQueries({ queryKey: ['scenario-packages'] });
      nav(`/scenarios/${res.scenario_id}/setup`);
    },
    onError: (e: unknown) => {
      setToast(errMsg(e));
    },
  });

  const deleteM = useMutation({
    mutationFn: (id: string) => deleteScenarioPackage(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scenario-packages'] });
      setConfirmDel(false);
      setSheet(null);
    },
    onError: (e: unknown) => {
      setToast(errMsg(e));
    },
  });

  const pkgs = listQ.data?.packages ?? [];

  function onEnter() {
    if (!sheet) return;
    if (sheet.lifecycle_phase === 'creation_running') {
      setToast('创作任务进行中，请稍候完成后再进入。');
      return;
    }
    if (canEnterChatPhase(sheet.lifecycle_phase)) {
      nav(`/scenarios/${sheet.scenario_id}/chat`);
    } else {
      nav(`/scenarios/${sheet.scenario_id}/setup`);
    }
    setSheet(null);
  }

  return (
    <div className="min-h-screen flex flex-col bg-paper">
      <AppHeader title="语言场景" backTo="/" backLabel="首页" />

      {toast && (
        <div className="mx-3 mt-2 rounded-md bg-ink px-3 py-2 text-xs text-white shadow-md">{toast}</div>
      )}

      <main className="flex-1 overflow-y-auto px-3 py-4 pb-36 max-w-lg mx-auto w-full">
        {listQ.isLoading && <p className="text-sm text-ink-soft">加载中…</p>}
        {listQ.isError && (
          <p className="text-sm text-danger">列表加载失败：{errMsg(listQ.error)}</p>
        )}
        {listQ.isSuccess && pkgs.length === 0 && (
          <div className="card text-center text-sm text-ink-soft py-10">
            还没有场景包。
            <br />
            点击下方「创建新场景」开始。
          </div>
        )}
        <ul className="space-y-3">
          {pkgs.map((p) => (
            <li key={p.scenario_id}>
              <button
                type="button"
                onClick={() => {
                  setToast(null);
                  setSheet(p);
                }}
                className="card w-full text-left transition hover:border-accent hover:shadow-md active:scale-[0.99]"
              >
                <div className="font-medium text-ink line-clamp-2">
                  {p.scenario_title?.trim() ? p.scenario_title : '（未命名场景）'}
                </div>
                <div className="mt-1 text-xs text-ink-soft font-mono">
                  {p.scenario_id.slice(0, 8)}… · {lifecyclePhaseLabel(p.lifecycle_phase)}
                </div>
                <div className="mt-1 text-[11px] text-ink-soft">更新于 {p.updated_at}</div>
              </button>
            </li>
          ))}
        </ul>
      </main>

      <footer className="fixed bottom-0 left-0 right-0 border-t border-border-subtle bg-paper/95 p-4 pb-[max(16px,env(safe-area-inset-bottom))] backdrop-blur">
        <div className="max-w-lg mx-auto w-full">
          <button
            type="button"
            className="btn-primary w-full"
            disabled={createM.isPending}
            onClick={() => {
              setToast(null);
              createM.mutate();
            }}
          >
            {createM.isPending ? '创建中…' : '创建新场景'}
          </button>
        </div>
      </footer>

      {sheet && !confirmDel && (
        <div
          className="fixed inset-0 z-50 flex flex-col justify-end bg-black/45 p-3"
          role="presentation"
          onClick={() => setSheet(null)}
        >
          <div
            className="max-w-lg mx-auto w-full rounded-t-xl bg-white p-4 shadow-xl"
            role="dialog"
            aria-modal
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-sm font-semibold text-ink line-clamp-2">
              {sheet.scenario_title?.trim() || '（未命名场景）'}
            </div>
            <p className="mt-1 text-xs text-ink-soft">{lifecyclePhaseLabel(sheet.lifecycle_phase)}</p>
            <div className="mt-4 flex flex-col gap-2">
              <button type="button" className="btn-primary w-full" onClick={onEnter}>
                进入场景
              </button>
              <button
                type="button"
                className="btn-danger w-full"
                onClick={() => setConfirmDel(true)}
              >
                删除场景
              </button>
              <button
                type="button"
                className="w-full rounded-md border border-border-subtle py-2.5 text-sm text-ink-soft"
                onClick={() => setSheet(null)}
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {sheet && confirmDel && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4">
          <div className="card max-w-sm w-full" role="dialog" aria-modal>
            <p className="text-sm text-ink leading-relaxed">
              是否确认删除该场景及<strong className="text-danger">全部数据</strong>？此操作不可恢复。
            </p>
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                className="flex-1 rounded-md border border-border-subtle py-2.5 text-sm"
                onClick={() => setConfirmDel(false)}
              >
                取消
              </button>
              <button
                type="button"
                className="btn-danger flex-1"
                disabled={deleteM.isPending}
                onClick={() => deleteM.mutate(sheet.scenario_id)}
              >
                {deleteM.isPending ? '删除中…' : '确认'}
              </button>
            </div>
          </div>
        </div>
      )}
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
