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
