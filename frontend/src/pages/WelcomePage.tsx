/**
 * P1 欢迎页（前端需求文档 §3.1）。
 */

import { useNavigate } from 'react-router-dom';

import { AppHeader } from '../components/layout/AppHeader';

export function WelcomePage() {
  const nav = useNavigate();

  return (
    <div className="min-h-screen flex flex-col bg-paper">
      <AppHeader title="自由语言世界" />

      <main className="flex-1 flex flex-col items-center px-5 pt-6 pb-28 max-w-lg mx-auto w-full">
        <div className="w-full rounded-xl border border-border-subtle bg-white p-6 shadow-sm">
          <h2 className="font-serif text-2xl text-ink leading-snug text-center">
            欢迎来到自由语言世界
          </h2>
          <p className="mt-4 text-sm text-ink-soft leading-relaxed text-center">
            把英语放回故事里。你描述想练的场景与目标，我们为你生成一段英文剧情——你是主角，NPC
            是同事、客户或朋友。在真实任务的对话里，自然练出实战表达。
          </p>

          <div
            className="mt-6 h-36 rounded-lg border border-dashed border-border-subtle bg-paper/80 flex items-center justify-center text-xs text-ink-soft"
            aria-hidden
          >
            主视觉占位
          </div>
        </div>
      </main>

      <footer className="fixed bottom-0 left-0 right-0 border-t border-border-subtle bg-paper/95 p-4 pb-[max(16px,env(safe-area-inset-bottom))] backdrop-blur">
        <div className="max-w-lg mx-auto w-full">
          <button type="button" className="btn-primary w-full" onClick={() => nav('/scenarios')}>
            知道了
          </button>
          <p className="mt-2 text-center text-[11px] text-ink-soft">进入「语言场景」清单（P2）</p>
        </div>
      </footer>
    </div>
  );
}
