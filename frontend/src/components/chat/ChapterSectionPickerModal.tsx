/**
 * P3a：章节 / 小节选择（确认后由父组件调用 POST enter）。
 */

import { useEffect, useState } from 'react';

type FrameworkChapter = {
  chapter_id: number;
  chapter_title: string;
  sections: Array<{ section_id: number; section_title: string }>;
};

export function ChapterSectionPickerModal(props: {
  open: boolean;
  onClose: () => void;
  chapters: FrameworkChapter[];
  initialChapterId: number;
  initialSectionId: number;
  onConfirm: (chapterId: number, sectionId: number) => void;
  busy?: boolean;
}) {
  const { open, onClose, chapters, initialChapterId, initialSectionId, onConfirm, busy } = props;
  const [chId, setChId] = useState(initialChapterId);
  const [secId, setSecId] = useState(initialSectionId);

  useEffect(() => {
    if (open) {
      setChId(initialChapterId);
      setSecId(initialSectionId);
    }
  }, [open, initialChapterId, initialSectionId]);

  if (!open) {
    return null;
  }

  const chapter = chapters.find((c) => c.chapter_id === chId) ?? chapters[0];
  const sections = chapter?.sections ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-0 sm:p-4" role="dialog" aria-modal="true">
      <div className="bg-paper w-full max-w-lg rounded-t-2xl sm:rounded-2xl shadow-xl max-h-[85vh] flex flex-col">
        <div className="px-4 py-3 border-b border-border-subtle flex justify-between items-center">
          <h2 className="text-sm font-semibold text-ink">章节列表</h2>
          <button type="button" className="text-xs text-ink-soft" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
          {chapters.map((ch) => (
            <div key={ch.chapter_id}>
              <p className="text-xs font-medium text-ink mb-2">
                第{ch.chapter_id}章 {ch.chapter_title}
              </p>
              <ul className="space-y-2">
                {ch.sections.map((sec) => {
                  const selected = chId === ch.chapter_id && secId === sec.section_id;
                  return (
                    <li key={`${ch.chapter_id}-${sec.section_id}`}>
                      <label className="flex items-start gap-2 cursor-pointer rounded-lg border border-border-subtle px-3 py-2 bg-white has-[:checked]:border-accent">
                        <input
                          type="radio"
                          name="section-pick"
                          className="mt-1"
                          checked={selected}
                          onChange={() => {
                            setChId(ch.chapter_id);
                            setSecId(sec.section_id);
                          }}
                        />
                        <span className="text-sm text-ink leading-snug">
                          {sec.section_id}. {sec.section_title}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
          {chapters.length === 0 && <p className="text-xs text-ink-soft">暂无章节数据。</p>}
        </div>
        <div className="px-4 py-3 border-t border-border-subtle flex gap-2">
          <button type="button" className="btn-secondary flex-1" onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="btn-primary flex-1"
            disabled={busy || sections.length === 0}
            onClick={() => onConfirm(chId, secId)}
          >
            {busy ? '进节中…' : '确认进入'}
          </button>
        </div>
      </div>
    </div>
  );
}
