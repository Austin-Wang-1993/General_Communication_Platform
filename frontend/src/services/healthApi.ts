/**
 * 健康检查 API（M0）。
 * 对应 API 文档 §1.1 GET /api/v1/health。
 */

import { apiRequest } from './apiClient';

export interface HealthResponse {
  ok: boolean;
  service: string;
  version: string;
  server_time: string;
  data_dir_writable: boolean;
  deepseek_configured: boolean;
}

export function getHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('GET', '/health', { timeoutMs: 5_000 });
}
