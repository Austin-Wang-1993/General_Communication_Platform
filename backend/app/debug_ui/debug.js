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

  // === M1：场景包管理 ===
  const listBtn = document.getElementById('btn-list-packages');
  const createBtn = document.getElementById('btn-create-package');
  const deleteBtn = document.getElementById('btn-delete-package');
  const listEl = document.getElementById('package-list');
  const detailOut = document.getElementById('out-package');
  const rawOut = document.getElementById('out-packages-raw');
  const selectedLabel = document.getElementById('selected-label');

  let selectedId = null;

  function setSelected(id, title) {
    selectedId = id;
    deleteBtn.disabled = !id;
    selectedLabel.textContent = id ? `· ${id.slice(0, 8)}… ${title ? '(' + title + ')' : ''}` : '（未选中）';
    document.querySelectorAll('#package-list li').forEach((li) => {
      li.classList.toggle('selected', li.dataset.id === id);
    });
  }

  async function refreshList(preserveSelected = false) {
    listEl.innerHTML = '<li class="placeholder">加载中…</li>';
    const result = await apiCall('GET', '/scenario-packages');
    renderResult(rawOut, result);
    if (!result.ok) {
      listEl.innerHTML = '<li class="placeholder">加载失败，看下方原始响应</li>';
      return;
    }
    const packages = (result.payload && result.payload.packages) || [];
    if (packages.length === 0) {
      listEl.innerHTML = '<li class="placeholder">无场景包；点"新建空包"创建一个</li>';
      setSelected(null, null);
      detailOut.innerHTML = '<span class="placeholder">在左侧点选某个场景包查看其 package.json</span>';
      return;
    }
    listEl.innerHTML = '';
    let stillSelected = false;
    for (const p of packages) {
      const li = document.createElement('li');
      li.dataset.id = p.scenario_id;
      const title = p.scenario_title || '(空标题)';
      li.innerHTML =
        `<div class="pkg-title">${escapeHtml(title)}</div>` +
        `<div class="pkg-meta">${escapeHtml(p.scenario_id.slice(0, 8))}… · ${escapeHtml(p.lifecycle_phase)} · ${escapeHtml(p.updated_at)}</div>`;
      li.addEventListener('click', () => loadDetail(p.scenario_id, title));
      listEl.appendChild(li);
      if (preserveSelected && p.scenario_id === selectedId) stillSelected = true;
    }
    if (!preserveSelected || !stillSelected) {
      setSelected(null, null);
      detailOut.innerHTML = '<span class="placeholder">在左侧点选某个场景包查看其 package.json</span>';
    }
  }

  async function loadDetail(id, title) {
    setSelected(id, title);
    detailOut.innerHTML = '<span class="placeholder">请求中…</span>';
    const result = await apiCall('GET', `/scenario-packages/${id}`);
    renderResult(rawOut, result);
    if (!result.ok) {
      detailOut.innerHTML = `<span class="status-err">加载失败</span>\n${escapeHtml(JSON.stringify(result.payload, null, 2))}`;
      return;
    }
    detailOut.textContent = JSON.stringify(result.payload, null, 2);
  }

  async function createPackage() {
    createBtn.disabled = true;
    try {
      const result = await apiCall('POST', '/scenario-packages', {});
      renderResult(rawOut, result);
      if (!result.ok) return;
      await refreshList(false);
      // 自动选中新建的那个
      if (result.payload && result.payload.scenario_id) {
        await loadDetail(result.payload.scenario_id, result.payload.scenario_title || '(空标题)');
      }
    } finally {
      createBtn.disabled = false;
    }
  }

  async function deleteSelected() {
    if (!selectedId) return;
    if (!confirm(`确认删除场景包 ${selectedId.slice(0, 8)}… ？此操作不可恢复。`)) return;
    deleteBtn.disabled = true;
    try {
      const result = await apiCall('DELETE', `/scenario-packages/${selectedId}`);
      renderResult(rawOut, result);
      if (!result.ok) return;
      setSelected(null, null);
      detailOut.innerHTML = '<span class="placeholder">已删除；刷新列表</span>';
      await refreshList(false);
    } finally {
      deleteBtn.disabled = false;
    }
  }

  if (listBtn) listBtn.addEventListener('click', () => refreshList(true));
  if (createBtn) createBtn.addEventListener('click', createPackage);
  if (deleteBtn) deleteBtn.addEventListener('click', deleteSelected);

  // 页面加载完自动拉一次列表
  if (listEl) {
    refreshList(false);
  }

  // === M2：五字段 commit-intake ===
  const commitBtn = document.getElementById('btn-commit-intake');
  const outIntake = document.getElementById('out-intake');
  const inScenarioTitle = document.getElementById('in-scenario-title');
  const inDisplayName = document.getElementById('in-display-name');
  const inSceneBrief = document.getElementById('in-scene-brief');
  const inGoalBrief = document.getElementById('in-goal-brief');
  const inVocab = document.getElementById('in-vocab');
  const inForceReset = document.getElementById('in-force-reset');

  if (commitBtn && outIntake) {
    commitBtn.addEventListener('click', async () => {
      if (!selectedId) {
        alert('请先在 ② 中点选一个场景包');
        return;
      }
      const body = {
        scenario_title: (inScenarioTitle && inScenarioTitle.value) || '',
        user_display_name: (inDisplayName && inDisplayName.value) || '',
        scene_brief: (inSceneBrief && inSceneBrief.value) || '',
        user_goal_brief: (inGoalBrief && inGoalBrief.value) || '',
        vocabulary_list: (inVocab && inVocab.value) || '',
        force_reset_creation: !!(inForceReset && inForceReset.checked),
      };
      commitBtn.disabled = true;
      outIntake.innerHTML = '<span class="placeholder">请求中（可能需数十秒）…</span>';
      try {
        const result = await apiCall(
          'POST',
          `/scenario-packages/${selectedId}/commit-intake`,
          body,
        );
        renderResult(rawOut, result);
        renderResult(outIntake, result);
        if (result.ok) {
          await refreshList(true);
          await loadDetail(selectedId, body.scenario_title);
        }
      } finally {
        commitBtn.disabled = false;
      }
    });
  }

  // 暴露给后续阶段扩展使用
  window.GcpDebug = { apiCall, renderResult, refreshList };
})();
