import { apiRequest } from './apiClient';

/** GET /scenario-packages/{id}/runtime */
export async function getRuntime(scenarioId: string): Promise<unknown> {
  return apiRequest('GET', `/scenario-packages/${scenarioId}/runtime`);
}

/** POST .../sections/{ch}/{sec}/enter */
export async function enterSection(
  scenarioId: string,
  chapterId: number,
  sectionId: number,
): Promise<unknown> {
  return apiRequest('POST', `/scenario-packages/${scenarioId}/sections/${chapterId}/${sectionId}/enter`, {
    body: {},
  });
}

export async function getSectionTurns(
  scenarioId: string,
  chapterId: number,
  sectionId: number,
  opts?: { limit?: number },
): Promise<unknown> {
  return apiRequest('GET', `/scenario-packages/${scenarioId}/sections/${chapterId}/${sectionId}/turns`, {
    query: opts?.limit != null ? { limit: opts.limit } : undefined,
  });
}

export async function postUserTurn(
  scenarioId: string,
  chapterId: number,
  sectionId: number,
  body: { content: string; recipient_id: string },
): Promise<unknown> {
  return apiRequest('POST', `/scenario-packages/${scenarioId}/sections/${chapterId}/${sectionId}/turns`, {
    body,
  });
}
