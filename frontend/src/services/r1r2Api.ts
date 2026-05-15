import { apiRequest } from './apiClient';

/** POST R1 回答提示 */
export async function postHint(
  scenarioId: string,
  chapterId: number,
  sectionId: number,
  body: { target_turn_id: string },
): Promise<unknown> {
  return apiRequest('POST', `/scenario-packages/${scenarioId}/sections/${chapterId}/${sectionId}/hints`, {
    body,
    timeoutMs: 180_000,
  });
}

/** GET 本节最新 hint（可能 204） */
export async function getHintLatest(
  scenarioId: string,
  chapterId: number,
  sectionId: number,
): Promise<unknown | undefined> {
  return apiRequest('GET', `/scenario-packages/${scenarioId}/sections/${chapterId}/${sectionId}/hints/latest`);
}

/** POST R2 本节复盘 */
export async function postSectionAnalytics(
  scenarioId: string,
  chapterId: number,
  sectionId: number,
): Promise<unknown> {
  return apiRequest('POST', `/scenario-packages/${scenarioId}/sections/${chapterId}/${sectionId}/analytics`, {
    body: {},
    timeoutMs: 180_000,
  });
}

/** GET 本节最新成功复盘（可能 204） */
export async function getSectionAnalyticsLatest(
  scenarioId: string,
  chapterId: number,
  sectionId: number,
): Promise<unknown | undefined> {
  return apiRequest('GET', `/scenario-packages/${scenarioId}/sections/${chapterId}/${sectionId}/analytics`);
}
