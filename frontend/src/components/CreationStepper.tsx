/**
 * 创作向导顶部三步：基本描述 → 框架生成 → 生成世界（与产品主链路一致）。
 */

type Step = 1 | 2 | 3;

const LABELS = ['基本描述', '框架生成', '生成世界'] as const;

export function CreationStepper({ current }: { current: Step }) {
  return (
    <div className="px-1 py-3">
      <div className="flex items-center justify-between gap-1 text-[11px]">
        {LABELS.map((label, idx) => {
          const step = (idx + 1) as Step;
          const active = step === current;
          const done = step < current;
          return (
            <div key={label} className="flex-1 flex flex-col items-center gap-1 min-w-0">
              <div
                className={[
                  'w-7 h-7 rounded-full flex items-center justify-center font-semibold shrink-0',
                  done ? 'bg-accent text-white' : active ? 'bg-ink text-paper' : 'bg-border-subtle text-ink-soft',
                ].join(' ')}
              >
                {done ? '✓' : step}
              </div>
              <span className={['text-center leading-tight truncate w-full', active ? 'text-ink font-medium' : 'text-ink-soft'].join(' ')}>
                {label}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-2 h-0.5 bg-border-subtle rounded overflow-hidden">
        <div
          className="h-full bg-accent transition-all duration-300"
          style={{ width: `${((current - 1) / 2) * 100}%` }}
        />
      </div>
    </div>
  );
}
