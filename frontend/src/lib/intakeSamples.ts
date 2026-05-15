/**
 * P2.1 五字段「样例底纹」：草稿包首次进入时预填，聚焦即清空；不修改则按样例提交。
 * 文案与 PRD §6.1 对齐；篇幅提示为**偏好**（最终以 §6.2 硬约束与 LLM 输出为准）。
 */

export const INTAKE_SAMPLES = {
  scenario_title: '产品经理职场英语：需求与排期演练（样例）',
  user_display_name: 'Alex（产品实习生）（样例）',
  scene_brief:
    '我是一名产品经理，希望在全英文的硅谷风格团队里练习口语：站会同步进度、和开发/design 对齐需求边界、用数据向老板解释排期 trade-off。场景偏真实职场，对话节奏紧凑，不要太童话式剧情。（为加快我本地联调时的渲染速度，请生成侧在合理范围内尽量控制全书章节数约 4 章、小节总数偏少。）（样例）',
  user_goal_brief:
    '能主持 stand-up、用英语澄清需求变更，并在评审里用简洁论据支撑我的方案。（样例）',
  vocabulary_list:
    'roadmap, sprint, backlog, trade-off, scope creep, stakeholder, rollout, mitigation（样例）',
} as const;

export type IntakeSampleField = keyof typeof INTAKE_SAMPLES;

export function isIntakeSampleText(field: IntakeSampleField, value: string): boolean {
  return value === INTAKE_SAMPLES[field];
}
