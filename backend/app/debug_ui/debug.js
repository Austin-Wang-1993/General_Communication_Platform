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
    const opts = { method };
    if (body !== undefined) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    }
    const url = API_BASE + path;
    const start = performance.now();
    let response;
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
    const text = await response.text();
    let payload;
    if (response.status === 204 || response.status === 205) {
      payload = { _empty_body: true, _message: '无响应体（常见于 GET …/hints/latest 或 GET …/analytics）' };
    } else if (!text) {
      payload = {};
    } else {
      try {
        payload = JSON.parse(text);
      } catch (e) {
        payload = { _raw: text };
      }
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

  /** 将 apiCall 失败结果压缩为一行，便于列表区 / alert 展示 */
  function formatApiErrorSummary(result) {
    if (result.kind === 'network') {
      return result.message || '网络错误';
    }
    const p = result.payload;
    if (p && typeof p === 'object' && p.error_code) {
      return String(result.status) + ' ' + String(p.error_code);
    }
    return String(result.status);
  }

  /** ⑥ 发送回合：收件人单选（来自本节 appearing_npc_ids + roster 显示名） */
  function clearTurnRecipientRadios(message) {
    const container = document.getElementById('turn-recipient-radios');
    if (!container) return;
    container.innerHTML =
      '<span class="placeholder">' +
      escapeHtml(message || '请先进节或 GET runtime 以加载本节可对话 NPC') +
      '</span>';
  }

  function fillTurnRecipientRadiosFromRuntimePayload(data) {
    const container = document.getElementById('turn-recipient-radios');
    if (!container || !data) return;
    const sn = data.section_narrative;
    const rosterRoot = data.character_roster;
    const ids = sn && Array.isArray(sn.appearing_npc_ids) ? sn.appearing_npc_ids : [];
    const chars =
      rosterRoot && Array.isArray(rosterRoot.characters) ? rosterRoot.characters : [];
    const nameById = {};
    chars.forEach((c) => {
      if (c && c.character_id) nameById[c.character_id] = c.name || c.character_id;
    });
    if (ids.length === 0) {
      clearTurnRecipientRadios('本节 appearing_npc_ids 为空，请检查 narrative.json');
      return;
    }
    container.innerHTML = '';
    ids.forEach((id, idx) => {
      const name = nameById[id] || id;
      const lab = document.createElement('label');
      lab.style.display = 'inline-flex';
      lab.style.alignItems = 'center';
      lab.style.gap = '6px';
      lab.style.cursor = 'pointer';
      const inp = document.createElement('input');
      inp.type = 'radio';
      inp.name = 'turn-recipient-npc';
      inp.value = id;
      if (idx === 0) inp.checked = true;
      lab.appendChild(inp);
      lab.appendChild(document.createTextNode(name + ' · ' + id));
      container.appendChild(lab);
    });
  }

  function getSelectedTurnRecipientId() {
    const el = document.querySelector('input[name="turn-recipient-npc"]:checked');
    return el ? el.value : '';
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
    const prevId = selectedId;
    selectedId = id;
    deleteBtn.disabled = !id;
    selectedLabel.textContent = id ? `· ${id.slice(0, 8)}… ${title ? '(' + title + ')' : ''}` : '（未选中）';
    document.querySelectorAll('#package-list li').forEach((li) => {
      li.classList.toggle('selected', li.dataset.id === id);
    });
    if (prevId !== id) {
      clearTurnRecipientRadios();
      const hintEl = document.getElementById('in-hint-target-turn-id');
      if (hintEl) hintEl.value = '';
    }
  }

  async function refreshList(preserveSelected = false) {
    try {
      listEl.innerHTML = '<li class="placeholder">加载中…</li>';
      const result = await apiCall('GET', '/scenario-packages');
      renderResult(rawOut, result);
      if (!result.ok) {
        const summary = formatApiErrorSummary(result);
        listEl.innerHTML =
          '<li class="placeholder status-err">加载失败：' +
          escapeHtml(summary) +
          '（请展开下方「最近 API 响应」）</li>';
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
    } catch (e) {
      const msg = e && e.message ? e.message : String(e);
      listEl.innerHTML =
        '<li class="placeholder status-err">页面脚本异常：' + escapeHtml(msg) + '</li>';
      if (rawOut) {
        rawOut.innerHTML =
          '<span class="status-err">异常</span>\n' + escapeHtml(msg);
      }
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
      if (!result.ok) {
        alert(
          '新建场景包失败：' +
            formatApiErrorSummary(result) +
            '\n请展开「最近 API 响应」查看完整 JSON。',
        );
        return;
      }
      await refreshList(false);
      // 自动选中新建的那个
      if (result.payload && result.payload.scenario_id) {
        await loadDetail(result.payload.scenario_id, result.payload.scenario_title || '(空标题)');
      }
    } catch (e) {
      const msg = e && e.message ? e.message : String(e);
      alert('新建场景包异常：' + msg);
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

  // === M3：framework Job ===
  const btnFramework = document.getElementById('btn-framework-job');
  const outFramework = document.getElementById('out-framework');
  let lastFrameworkJobId = null;
  let fwPollTimer = null;

  function stopFwPoll() {
    if (fwPollTimer) {
      clearInterval(fwPollTimer);
      fwPollTimer = null;
    }
  }

  if (btnFramework && outFramework) {
    btnFramework.addEventListener('click', async () => {
      if (!selectedId) {
        alert('请先在 ② 中点选一个场景包');
        return;
      }
      stopFwPoll();
      lastFrameworkJobId = null;
      btnFramework.disabled = true;
      outFramework.innerHTML = '<span class="placeholder">启动 Job 中…</span>';
      try {
        const result = await apiCall('POST', `/scenario-packages/${selectedId}/jobs/framework`, {});
        renderResult(rawOut, result);
        renderResult(outFramework, result);
        if (result.ok && result.payload && result.payload.job_id) {
          lastFrameworkJobId = result.payload.job_id;
          fwPollTimer = setInterval(async () => {
            if (!selectedId || !lastFrameworkJobId) return;
            const r = await apiCall(
              'GET',
              `/scenario-packages/${selectedId}/jobs/${lastFrameworkJobId}`,
            );
            renderResult(rawOut, r);
            renderResult(outFramework, r);
            if (r.ok && r.payload && ['succeeded', 'failed', 'canceled'].includes(r.payload.status)) {
              stopFwPoll();
              await refreshList(true);
              const titleEl = document.querySelector('#package-list li.selected .pkg-title');
              const t = titleEl ? titleEl.textContent : '';
              await loadDetail(selectedId, t);
            }
          }, 1200);
        }
      } finally {
        btnFramework.disabled = false;
      }
    });
  }

  // === M4：world Job + cancel ===
  const btnWorld = document.getElementById('btn-world-job');
  const btnWorldCancel = document.getElementById('btn-world-cancel');
  const outWorld = document.getElementById('out-world');
  const inWorldForce = document.getElementById('in-world-force');
  let lastWorldJobId = null;
  let worldPollTimer = null;

  function stopWorldPoll() {
    if (worldPollTimer) {
      clearInterval(worldPollTimer);
      worldPollTimer = null;
    }
  }

  function syncWorldCancelBtn() {
    if (btnWorldCancel) {
      btnWorldCancel.disabled = !lastWorldJobId;
    }
  }

  if (btnWorld && outWorld) {
    btnWorld.addEventListener('click', async () => {
      if (!selectedId) {
        alert('请先在 ② 中点选一个场景包');
        return;
      }
      stopWorldPoll();
      lastWorldJobId = null;
      syncWorldCancelBtn();
      btnWorld.disabled = true;
      outWorld.innerHTML = '<span class="placeholder">启动 world Job 中…</span>';
      try {
        const body = {
          force_regenerate: !!(inWorldForce && inWorldForce.checked),
        };
        const result = await apiCall('POST', `/scenario-packages/${selectedId}/jobs/world`, body);
        renderResult(rawOut, result);
        renderResult(outWorld, result);
        if (result.ok && result.payload && result.payload.job_id) {
          lastWorldJobId = result.payload.job_id;
          syncWorldCancelBtn();
          worldPollTimer = setInterval(async () => {
            if (!selectedId || !lastWorldJobId) return;
            const r = await apiCall(
              'GET',
              `/scenario-packages/${selectedId}/jobs/${lastWorldJobId}`,
            );
            renderResult(rawOut, r);
            renderResult(outWorld, r);
            if (r.ok && r.payload && ['succeeded', 'failed', 'canceled'].includes(r.payload.status)) {
              stopWorldPoll();
              await refreshList(true);
              const titleEl = document.querySelector('#package-list li.selected .pkg-title');
              const t = titleEl ? titleEl.textContent : '';
              await loadDetail(selectedId, t);
            }
          }, 1200);
        }
      } finally {
        btnWorld.disabled = false;
      }
    });
  }

  if (btnWorldCancel && rawOut) {
    btnWorldCancel.addEventListener('click', async () => {
      if (!selectedId || !lastWorldJobId) {
        alert('请先启动 world Job 以获取 job_id');
        return;
      }
      btnWorldCancel.disabled = true;
      try {
        const result = await apiCall(
          'POST',
          `/scenario-packages/${selectedId}/jobs/${lastWorldJobId}/cancel`,
        );
        renderResult(rawOut, result);
        if (outWorld) renderResult(outWorld, result);
        stopWorldPoll();
        if (result.ok) {
          lastWorldJobId = null;
          syncWorldCancelBtn();
          await refreshList(true);
          const titleEl = document.querySelector('#package-list li.selected .pkg-title');
          const t = titleEl ? titleEl.textContent : '';
          await loadDetail(selectedId, t);
        }
      } finally {
        syncWorldCancelBtn();
      }
    });
  }

  // === M5：进节 + runtime ===
  const btnEnterSection = document.getElementById('btn-enter-section');
  const btnGetRuntime = document.getElementById('btn-get-runtime');
  const outRuntime = document.getElementById('out-runtime');
  const inEnterCh = document.getElementById('in-enter-ch');
  const inEnterSec = document.getElementById('in-enter-sec');

  if (btnEnterSection && outRuntime) {
    btnEnterSection.addEventListener('click', async () => {
      if (!selectedId) {
        alert('请先在 ② 中点选一个场景包');
        return;
      }
      const ch = parseInt((inEnterCh && inEnterCh.value) || '1', 10);
      const sec = parseInt((inEnterSec && inEnterSec.value) || '1', 10);
      btnEnterSection.disabled = true;
      outRuntime.innerHTML = '<span class="placeholder">进节请求中（可能需数十秒，自动开场调 LLM）…</span>';
      try {
        const result = await apiCall(
          'POST',
          `/scenario-packages/${selectedId}/sections/${ch}/${sec}/enter`,
          {},
        );
        renderResult(rawOut, result);
        renderResult(outRuntime, result);
        if (result.ok && result.payload) {
          fillTurnRecipientRadiosFromRuntimePayload(result.payload);
          await refreshList(true);
          const titleEl = document.querySelector('#package-list li.selected .pkg-title');
          const t = titleEl ? titleEl.textContent : '';
          await loadDetail(selectedId, t);
        }
      } finally {
        btnEnterSection.disabled = false;
      }
    });
  }

  if (btnGetRuntime && outRuntime) {
    btnGetRuntime.addEventListener('click', async () => {
      if (!selectedId) {
        alert('请先在 ② 中点选一个场景包');
        return;
      }
      btnGetRuntime.disabled = true;
      try {
        const result = await apiCall('GET', `/scenario-packages/${selectedId}/runtime`);
        renderResult(rawOut, result);
        renderResult(outRuntime, result);
        if (result.ok && result.payload) {
          fillTurnRecipientRadiosFromRuntimePayload(result.payload);
        }
      } finally {
        btnGetRuntime.disabled = false;
      }
    });
  }

  const btnPostTurn = document.getElementById('btn-post-turn');
  const btnGetTurns = document.getElementById('btn-get-turns');
  const btnAutoOpener = document.getElementById('btn-auto-opener');
  const inTurnContent = document.getElementById('in-turn-content');
  const inTurnsLimit = document.getElementById('in-turns-limit');

  function onEnterChSecChanged() {
    clearTurnRecipientRadios('章/节已变更，请重新进节或 GET runtime 以刷新 NPC 列表');
    const hintEl = document.getElementById('in-hint-target-turn-id');
    if (hintEl) hintEl.value = '';
  }
  if (inEnterCh) inEnterCh.addEventListener('change', onEnterChSecChanged);
  if (inEnterSec) inEnterSec.addEventListener('change', onEnterChSecChanged);

  if (btnPostTurn && outRuntime) {
    btnPostTurn.addEventListener('click', async () => {
      if (!selectedId) {
        alert('请先在 ② 中点选一个场景包');
        return;
      }
      const ch = parseInt((inEnterCh && inEnterCh.value) || '1', 10);
      const sec = parseInt((inEnterSec && inEnterSec.value) || '1', 10);
      const content = (inTurnContent && inTurnContent.value) || '';
      const recipient_id = getSelectedTurnRecipientId();
      if (!recipient_id) {
        alert('请先 POST 进节或 GET runtime，在本节 NPC 单选项中选择收件人后再发送。');
        return;
      }
      btnPostTurn.disabled = true;
      try {
        const result = await apiCall(
          'POST',
          `/scenario-packages/${selectedId}/sections/${ch}/${sec}/turns`,
          { content, recipient_id },
        );
        renderResult(rawOut, result);
        renderResult(outRuntime, result);
        if (result.ok) {
          await refreshList(true);
          const titleEl = document.querySelector('#package-list li.selected .pkg-title');
          const t = titleEl ? titleEl.textContent : '';
          await loadDetail(selectedId, t);
        }
      } finally {
        btnPostTurn.disabled = false;
      }
    });
  }

  if (btnGetTurns && outRuntime) {
    btnGetTurns.addEventListener('click', async () => {
      if (!selectedId) {
        alert('请先在 ② 中点选一个场景包');
        return;
      }
      const ch = parseInt((inEnterCh && inEnterCh.value) || '1', 10);
      const sec = parseInt((inEnterSec && inEnterSec.value) || '1', 10);
      const limRaw = inTurnsLimit && inTurnsLimit.value;
      const lim = limRaw ? parseInt(limRaw, 10) : null;
      const q = lim && !Number.isNaN(lim) ? `?limit=${lim}` : '';
      btnGetTurns.disabled = true;
      try {
        const result = await apiCall(
          'GET',
          `/scenario-packages/${selectedId}/sections/${ch}/${sec}/turns${q}`,
        );
        renderResult(rawOut, result);
        renderResult(outRuntime, result);
      } finally {
        btnGetTurns.disabled = false;
      }
    });
  }

  if (btnAutoOpener && outRuntime) {
    btnAutoOpener.addEventListener('click', async () => {
      if (!selectedId) {
        alert('请先在 ② 中点选一个场景包');
        return;
      }
      const ch = parseInt((inEnterCh && inEnterCh.value) || '1', 10);
      const sec = parseInt((inEnterSec && inEnterSec.value) || '1', 10);
      btnAutoOpener.disabled = true;
      try {
        const result = await apiCall(
          'POST',
          `/scenario-packages/${selectedId}/sections/${ch}/${sec}/auto-opener`,
          {},
        );
        renderResult(rawOut, result);
        renderResult(outRuntime, result);
        if (result.ok) {
          await refreshList(true);
          const titleEl = document.querySelector('#package-list li.selected .pkg-title');
          const t = titleEl ? titleEl.textContent : '';
          await loadDetail(selectedId, t);
        }
      } finally {
        btnAutoOpener.disabled = false;
      }
    });
  }

  // === ⑦ R1 hints + R2 analytics（与 ⑥ 共用章/节） ===
  const outR1r2 = document.getElementById('out-r1r2');
  const inHintTargetTurnId = document.getElementById('in-hint-target-turn-id');
  const btnHintFillTarget = document.getElementById('btn-hint-fill-target');
  const btnPostHint = document.getElementById('btn-post-hint');
  const btnGetHintLatest = document.getElementById('btn-get-hint-latest');
  const btnPostAnalytics = document.getElementById('btn-post-analytics');
  const btnGetAnalytics = document.getElementById('btn-get-analytics');

  function pickLastAwaitingNpcTurnId(turnsArr) {
    if (!Array.isArray(turnsArr)) return '';
    for (let i = turnsArr.length - 1; i >= 0; i -= 1) {
      const t = turnsArr[i];
      if (t && t.expects_user_response && t.speaker_id && t.speaker_id !== 'user') {
        return String(t.turn_id || '');
      }
    }
    return '';
  }

  if (btnHintFillTarget && inHintTargetTurnId && outR1r2) {
    btnHintFillTarget.addEventListener('click', async () => {
      if (!selectedId) {
        alert('请先在 ② 中点选一个场景包');
        return;
      }
      const ch = parseInt((inEnterCh && inEnterCh.value) || '1', 10);
      const sec = parseInt((inEnterSec && inEnterSec.value) || '1', 10);
      btnHintFillTarget.disabled = true;
      try {
        const result = await apiCall(
          'GET',
          `/scenario-packages/${selectedId}/sections/${ch}/${sec}/turns`,
        );
        renderResult(rawOut, result);
        renderResult(outR1r2, result);
        if (result.ok && result.payload && Array.isArray(result.payload.turns)) {
          const tid = pickLastAwaitingNpcTurnId(result.payload.turns);
          if (tid) {
            inHintTargetTurnId.value = tid;
          } else {
            alert('未找到 expects_user_response 且说话人非 user 的回合；请先对话到等待用户状态。');
          }
        }
      } finally {
        btnHintFillTarget.disabled = false;
      }
    });
  }

  if (btnPostHint && outR1r2) {
    btnPostHint.addEventListener('click', async () => {
      if (!selectedId) {
        alert('请先在 ② 中点选一个场景包');
        return;
      }
      const ch = parseInt((inEnterCh && inEnterCh.value) || '1', 10);
      const sec = parseInt((inEnterSec && inEnterSec.value) || '1', 10);
      const target_turn_id = (inHintTargetTurnId && inHintTargetTurnId.value.trim()) || '';
      if (!target_turn_id) {
        alert('请填写 target_turn_id，或先点「从 GET turns 填充」。');
        return;
      }
      btnPostHint.disabled = true;
      outR1r2.innerHTML = '<span class="placeholder">POST hints 请求中（调 LLM）…</span>';
      try {
        const result = await apiCall(
          'POST',
          `/scenario-packages/${selectedId}/sections/${ch}/${sec}/hints`,
          { target_turn_id },
        );
        renderResult(rawOut, result);
        renderResult(outR1r2, result);
      } finally {
        btnPostHint.disabled = false;
      }
    });
  }

  if (btnGetHintLatest && outR1r2) {
    btnGetHintLatest.addEventListener('click', async () => {
      if (!selectedId) {
        alert('请先在 ② 中点选一个场景包');
        return;
      }
      const ch = parseInt((inEnterCh && inEnterCh.value) || '1', 10);
      const sec = parseInt((inEnterSec && inEnterSec.value) || '1', 10);
      btnGetHintLatest.disabled = true;
      try {
        const result = await apiCall(
          'GET',
          `/scenario-packages/${selectedId}/sections/${ch}/${sec}/hints/latest`,
        );
        renderResult(rawOut, result);
        renderResult(outR1r2, result);
      } finally {
        btnGetHintLatest.disabled = false;
      }
    });
  }

  if (btnPostAnalytics && outR1r2) {
    btnPostAnalytics.addEventListener('click', async () => {
      if (!selectedId) {
        alert('请先在 ② 中点选一个场景包');
        return;
      }
      const ch = parseInt((inEnterCh && inEnterCh.value) || '1', 10);
      const sec = parseInt((inEnterSec && inEnterSec.value) || '1', 10);
      btnPostAnalytics.disabled = true;
      outR1r2.innerHTML = '<span class="placeholder">POST analytics 请求中（调 LLM）…</span>';
      try {
        const result = await apiCall(
          'POST',
          `/scenario-packages/${selectedId}/sections/${ch}/${sec}/analytics`,
          {},
        );
        renderResult(rawOut, result);
        renderResult(outR1r2, result);
      } finally {
        btnPostAnalytics.disabled = false;
      }
    });
  }

  if (btnGetAnalytics && outR1r2) {
    btnGetAnalytics.addEventListener('click', async () => {
      if (!selectedId) {
        alert('请先在 ② 中点选一个场景包');
        return;
      }
      const ch = parseInt((inEnterCh && inEnterCh.value) || '1', 10);
      const sec = parseInt((inEnterSec && inEnterSec.value) || '1', 10);
      btnGetAnalytics.disabled = true;
      try {
        const result = await apiCall(
          'GET',
          `/scenario-packages/${selectedId}/sections/${ch}/${sec}/analytics`,
        );
        renderResult(rawOut, result);
        renderResult(outR1r2, result);
      } finally {
        btnGetAnalytics.disabled = false;
      }
    });
  }

  window.GcpDebug = { apiCall, renderResult, refreshList };
})();
