/**
 * GCP 调试页 · 原生 JS（无构建工具）
 * M0：仅实现健康检查；M1+ 阶段会扩充其他智能体调用。
 *
 * 设计原则与技术方案 §10.1 一致：
 * - 单页 HTML + 原生 JS，不引入框架
 * - 所有请求统一打 /api/v1/...
 * - 输出区域显示完整 JSON 响应或错误
 */

(function () {
  'use strict';

  /** 统一的 API 基础路径——与前端 SPA 同域同前缀 */
  const API_BASE = '/api/v1';

  /** 通用 fetch 封装：处理 JSON 响应与错误 */
  async function apiCall(method, path, body) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body !== undefined) {
      opts.body = JSON.stringify(body);
    }
    const url = API_BASE + path;
    const start = performance.now();
    let response, payload;
    try {
      response = await fetch(url, opts);
    } catch (e) {
      return {
        ok: false,
        kind: 'network',
        status: 0,
        durationMs: Math.round(performance.now() - start),
        message: e && e.message ? e.message : String(e),
        url,
      };
    }
    const durationMs = Math.round(performance.now() - start);
    try {
      payload = await response.json();
    } catch (e) {
      payload = { _raw: await response.text() };
    }
    return {
      ok: response.ok,
      kind: response.ok ? 'success' : 'http_error',
      status: response.status,
      durationMs,
      payload,
      url,
    };
  }

  /** 渲染响应到指定输出区 */
  function renderResult(outEl, result) {
    const statusLine = result.ok
      ? `<span class="status-ok">✓ ${result.status} OK</span>` +
        ` <span class="placeholder">(${result.durationMs}ms)</span>\n${result.url}\n\n`
      : `<span class="status-err">✗ ${result.kind === 'network' ? 'Network Error' : result.status + ' ' + (result.payload && result.payload.error_code ? result.payload.error_code : 'Error')}</span>` +
        ` <span class="placeholder">(${result.durationMs}ms)</span>\n${result.url}\n\n`;
    const body = result.kind === 'network'
      ? result.message
      : JSON.stringify(result.payload, null, 2);
    outEl.innerHTML = statusLine + escapeHtml(body);
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // === M0：健康检查按钮 ===
  const healthBtn = document.getElementById('btn-health');
  const healthOut = document.getElementById('out-health');
  if (healthBtn && healthOut) {
    healthBtn.addEventListener('click', async () => {
      healthBtn.disabled = true;
      healthOut.innerHTML = '<span class="placeholder">请求中…</span>';
      try {
        const result = await apiCall('GET', '/health');
        renderResult(healthOut, result);
      } finally {
        healthBtn.disabled = false;
      }
    });
  }

  // 暴露给后续阶段扩展使用
  window.GcpDebug = { apiCall, renderResult };
})();
