import { apiRequest } from './apiClient';

/** GET /debug/raw-file（§7.2）：白名单 JSON 只读。 */
export async function getRawJsonFile(scenarioId: string, relpath: string): Promise<unknown> {
  return apiRequest('GET', '/debug/raw-file', {
    query: { scenario_id: scenarioId, relpath },
  });
}
