import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';

type AppHeaderProps = {
  title?: string;
  /** 左侧返回目标；不传则无返回按钮 */
  backTo?: string;
  backLabel?: string;
  /** 标题右侧、调试入口左侧的扩展区（如章节按钮） */
  end?: ReactNode;
};

/**
 * 顶栏：调试模式入口（前端需求 G1）+ 可选返回。
 */
export function AppHeader({ title, backTo, backLabel = '返回', end }: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-40 flex items-center gap-2 border-b border-border-subtle bg-paper/95 px-3 py-3 backdrop-blur supports-[padding:max(0px)]:pt-[max(12px,env(safe-area-inset-top))]">
      <div className="min-w-0 flex-1 flex items-center gap-2">
        {backTo && (
          <Link
            to={backTo}
            className="shrink-0 rounded-md px-2 py-1.5 text-sm text-ink-soft hover:bg-white hover:text-ink"
          >
            ← {backLabel}
          </Link>
        )}
        {title && <h1 className="truncate text-base font-semibold text-ink">{title}</h1>}
      </div>
      {end}
      <a
        href={`${typeof window !== 'undefined' ? window.location.origin : ''}/debug/`}
        className="shrink-0 rounded-md border border-border-subtle bg-white px-2.5 py-1.5 text-xs font-medium text-ink-soft hover:border-accent hover:text-accent"
      >
        调试模式
      </a>
    </header>
  );
}
