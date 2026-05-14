/**
 * P1 欢迎页（M0 占位实现）。
 *
 * 当前阶段：
 * - 展示标题 + 简介 + 主按钮（按钮目前调健康检查作为 M0 验收信号；
 *   M6 阶段会把按钮改为 P1-02-01「知道了」→ 跳 /scenarios）
 *
 * 视觉基调：干净书页风（暖白底 + 深灰文字 + 暖橘强调色）。
 */

import { useState } from 'react';

import { getHealth, type HealthResponse } from '../services/healthApi';
import { ApiError, NetworkError, TimeoutError } from '../services/apiClient';

type ProbeState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'ok'; data: HealthResponse }
  | { kind: 'err'; message: string };

export function WelcomePage() {
  const [state, setState] = useState<ProbeState>({ kind: 'idle' });

  async function runHealthCheck() {
    setState({ kind: 'loading' });
    try {
      const data = await getHealth();
      setState({ kind: 'ok', data });
    } catch (e) {
      let msg: string;
      if (e instanceof ApiError) {
        msg = `${e.errorCode}：${e.message}`;
      } else if (e instanceof TimeoutError || e instanceof NetworkError) {
        msg = e.message;
      } else {
        msg = String(e);
      }
      setState({ kind: 'err', message: msg });
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="card max-w-md w-full">
          <h1 className="font-serif text-2xl text-ink leading-snug">
            欢迎来到自由语言世界
          </h1>
          <p className="mt-3 text-sm text-ink-soft leading-relaxed">
            把英语放回故事里。你描述想练的场景与目标，我们为你生成一段英文剧情——你是主角，NPC
            是同事、客户或朋友。在真实任务的对话里，自然练出实战表达。
          </p>

          <hr className="my-5 border-border-subtle" />

          <div className="text-xs uppercase tracking-wider text-ink-soft mb-2">
            M0 健康检查
          </div>
          <button
            type="button"
            className="btn-primary w-full"
            disabled={state.kind === 'loading'}
            onClick={runHealthCheck}
          >
            {state.kind === 'loading' ? '请求中…' : '检查后端是否就绪'}
          </button>

          <div className="mt-4 min-h-[60px]">
            {state.kind === 'idle' && (
              <div className="text-xs text-ink-soft italic">
                点击上方按钮调用 GET /api/v1/health
              </div>
            )}
            {state.kind === 'ok' && <HealthOk data={state.data} />}
            {state.kind === 'err' && (
              <div className="text-sm text-danger break-words">
                ✗ {state.message}
              </div>
            )}
          </div>
        </div>
      </main>

      <footer className="text-center text-xs text-ink-soft py-4">
        M0 骨架 · 详见 README 与 docs/operations/01-腾讯云部署指南.md
      </footer>
    </div>
  );
}

function HealthOk({ data }: { data: HealthResponse }) {
  return (
    <div className="space-y-2 text-sm">
      <div className="text-ok font-semibold">✓ 后端 OK</div>
      <ul className="text-ink-soft text-xs space-y-1">
        <li>
          <span className="font-mono">version:</span> {data.version}
        </li>
        <li>
          <span className="font-mono">server_time:</span> {data.server_time}
        </li>
        <li>
          <span className="font-mono">data_dir_writable:</span>{' '}
          {String(data.data_dir_writable)}
        </li>
        <li>
          <span className="font-mono">deepseek_configured:</span>{' '}
          {data.deepseek_configured ? '✓' : '✗'}
        </li>
      </ul>
    </div>
  );
}
