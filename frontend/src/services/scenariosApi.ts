import { apiRequest } from './apiClient';
import type { JobStatusResponse, PackageDetail, PackageSummary } from '../types/scenario';

export async function listScenarioPackages(): Promise<{ packages: PackageSummary[] }> {
  return apiRequest('GET', '/scenario-packages');
}

export async function createScenarioPackage(body?: {
  scenario_title_hint?: string;
}): Promise<{
  scenario_id: string;
  lifecycle_phase: string;
  scenario_title: string;
  created_at: string;
  updated_at: string;
}> {
  return apiRequest('POST', '/scenario-packages', { body: body ?? {} });
}

export async function deleteScenarioPackage(scenarioId: string): Promise<void> {
  await apiRequest('DELETE', `/scenario-packages/${scenarioId}`);
}

export async function getScenarioPackage(scenarioId: string): Promise<PackageDetail> {
  return apiRequest('GET', `/scenario-packages/${scenarioId}`);
}

export async function commitIntake(
  scenarioId: string,
  body: {
    scenario_title: string;
    user_display_name: string;
    scene_brief: string;
    user_goal_brief: string;
    vocabulary_list: string;
    force_reset_creation?: boolean;
  },
): Promise<unknown> {
  return apiRequest('POST', `/scenario-packages/${scenarioId}/commit-intake`, { body });
}

export async function startFrameworkJob(scenarioId: string): Promise<JobStatusResponse> {
  return apiRequest('POST', `/scenario-packages/${scenarioId}/jobs/framework`, {
    body: {},
    timeoutMs: 60_000,
  });
}

export async function startWorldJob(
  scenarioId: string,
  body?: { force_regenerate?: boolean },
): Promise<JobStatusResponse> {
  return apiRequest('POST', `/scenario-packages/${scenarioId}/jobs/world`, {
    body: body ?? {},
    timeoutMs: 60_000,
  });
}

export async function getJob(scenarioId: string, jobId: string): Promise<JobStatusResponse> {
  return apiRequest('GET', `/scenario-packages/${scenarioId}/jobs/${jobId}`);
}

export async function cancelJob(scenarioId: string, jobId: string): Promise<unknown> {
  return apiRequest('POST', `/scenario-packages/${scenarioId}/jobs/${jobId}/cancel`, {
    body: {},
  });
}
