/**
 * 统一 API 客户端封装。
 * 对齐 docs/engineering/02-代码架构与目录约定.md §3.4 与 §4。
 *
 * 设计要点：
 * - 所有请求统一通过本文件；不在业务 hook / 组件里裸调 fetch。
 * - 后端响应失败时（4xx / 5xx）抛出结构化 ApiError，包含 error_code（API 文档 §0.7）。
 * - 单次请求超时统一 180s（与技术方案 §11.6 超时链对齐）。
 * - snake_case 字段不做改写——前后端契约一致（架构文档 §4.1）。
 */

const API_BASE = (import.meta.env.VITE_API_BASE || '') + '/api/v1';

const DEFAULT_TIMEOUT_MS = 180_000;

export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: string;
  readonly details: unknown;

  constructor(
    status: number,
    errorCode: string,
    message: string,
    details: unknown = null,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errorCode = errorCode;
    this.details = details;
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NetworkError';
  }
}

export class TimeoutError extends Error {
  constructor() {
    super('请求超时，请检查网络或重试');
    this.name = 'TimeoutError';
  }
}

type Method = 'GET' | 'POST' | 'DELETE' | 'PATCH' | 'PUT';

interface RequestOptions {
  body?: unknown;
  query?: Record<string, string | number | undefined | null>;
  timeoutMs?: number;
  signal?: AbortSignal;
}

export async function apiRequest<TResponse = unknown>(
  method: Method,
  path: string,
  options: RequestOptions = {},
): Promise<TResponse> {
  const url = buildUrl(path, options.query);
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  // 允许调用者再次绑定外部 signal
  if (options.signal) {
    options.signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  const init: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
    signal: controller.signal,
  };
  if (options.body !== undefined) {
    init.body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (e: unknown) {
    clearTimeout(timer);
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new TimeoutError();
    }
    throw new NetworkError(e instanceof Error ? e.message : String(e));
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { _raw: text };
    }
  }

  if (!response.ok) {
    const errPayload = (payload && typeof payload === 'object' ? payload : {}) as {
      error_code?: string;
      message?: string;
      details?: unknown;
    };
    throw new ApiError(
      response.status,
      errPayload.error_code || 'unknown_error',
      errPayload.message || `请求失败（HTTP ${response.status}）`,
      errPayload.details ?? null,
    );
  }

  return payload as TResponse;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const base = API_BASE.replace(/\/+$/, '');
  const cleanPath = path.startsWith('/') ? path : '/' + path;
  let url = base + cleanPath;
  if (query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null) {
        params.append(k, String(v));
      }
    }
    const qs = params.toString();
    if (qs) url += '?' + qs;
  }
  return url;
}
