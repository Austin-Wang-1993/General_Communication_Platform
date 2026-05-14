#!/usr/bin/env bash
# 通用英语对话练习 · 拉取并重启脚本
#
# 用法：
#   ./deploy/pull-and-restart.sh                      # 拉 main 并重启
#   ./deploy/pull-and-restart.sh cursor/<feature-分支>  # 拉指定远端分支并重启
#
# 设计与 docs/engineering/01-技术方案.md §11.2 双分支工作流对齐。
#
# ---------------------------------------------------------------------------
# 为何会出现「调试页/前端变了，但新 API 仍 404」？
#
# - Nginx 对 /debug/、前端 dist 多为「直接读磁盘文件」；git 更新后立刻变新。
# - /api/ 反代到本机 uvicorn；Python 进程不重启则仍驻留在旧代码内存里。
# - 旧版脚本仅用 git reset --hard 而不切换分支名时，容易与「我到底在哪条分支」
#   的认知不一致；本脚本改为 git checkout -B，强制本地分支名 = 参数分支名。
#
# 若未注册 gcp-backend.service，本脚本会**失败退出**（避免误以为部署成功）。
# ---------------------------------------------------------------------------
#
# 内部步骤：
#   0) 前置检查（git 仓库、git/curl/sudo、远端分支存在）
#   1) git fetch + git checkout -B <分支> origin/<分支>
#   2) 记录 requirements / package-lock 哈希
#   3) venv + pip install（按需；GCP_SYNC_FULL=1 时每次全量 pip）
#   4) npm ci + npm run build（按需；GCP_SYNC_FULL=1 时每次 npm ci）
#   5) systemctl restart gcp-backend（必须已注册单元）+ 本机健康检查
#   6) systemctl reload nginx（若已安装）
#   7) OpenAPI 路由探测（仅供参考；M0/main 无 scenario-packages 属正常）
#   8) 打印摘要（分支、commit、最近一条提交说明）

set -euo pipefail

BRANCH="${1:-main}"
REPO_DIR="${GCP_REPO_DIR:-/opt/gcp}"
BACKEND_DIR="${REPO_DIR}/backend"
FRONTEND_DIR="${REPO_DIR}/frontend"
VENV_DIR="${BACKEND_DIR}/.venv"
LOCAL_HEALTH_URL="${LOCAL_HEALTH_URL:-http://127.0.0.1:8000/api/v1/health}"
LOCAL_OPENAPI_URL="${LOCAL_OPENAPI_URL:-http://127.0.0.1:8000/openapi.json}"
# GCP_SYNC_FULL=1：每次均 pip install -r + npm ci（更慢、更稳；server-one-shot-sync.sh 默认开启）
SYNC_FULL="${GCP_SYNC_FULL:-0}"

color() {
    local code="$1"; shift
    printf "\033[%sm%s\033[0m\n" "$code" "$*"
}
info()  { color "1;36" "[$(date +%T)] $*"; }
ok()    { color "1;32" "[$(date +%T)] ✓ $*"; }
warn()  { color "1;33" "[$(date +%T)] ⚠ $*"; }
err()   { color "1;31" "[$(date +%T)] ✗ $*"; }

# === 0. 前置检查 ===
for cmd in git curl sudo; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        err "缺少命令「${cmd}」，请先安装后再执行本脚本。"
        exit 1
    fi
done

if ! git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    err "「${REPO_DIR}」不是 git 工作区（可通过环境变量 GCP_REPO_DIR 指向仓库根）。"
    exit 1
fi

cd "$REPO_DIR"

info "检查远端是否存在分支 origin/${BRANCH}"
if ! git ls-remote --heads origin "${BRANCH}" | grep -q .; then
    err "远端不存在分支「${BRANCH}」。请核对：拼写、是否已 push、大小写是否与 GitHub 一致。"
    exit 1
fi

# === 1. 记录变动前的依赖文件 hash ===
BEFORE_REQ=""
BEFORE_LOCK=""
[ -f "${BACKEND_DIR}/requirements.txt" ] && BEFORE_REQ=$(sha256sum "${BACKEND_DIR}/requirements.txt" | awk '{print $1}')
[ -f "${FRONTEND_DIR}/package-lock.json" ] && BEFORE_LOCK=$(sha256sum "${FRONTEND_DIR}/package-lock.json" | awk '{print $1}')

# === 2. 拉取并对齐分支（checkout -B：同步工作区 + 本地分支名，避免「磁盘已是新代码但分支名仍停在旧 feature」）===
info "拉取并对齐到 origin/${BRANCH}"
git fetch origin "${BRANCH}"
if ! git checkout -B "${BRANCH}" "origin/${BRANCH}"; then
    err "git checkout -B 失败，请检查工作区是否被占用或权限问题。"
    exit 1
fi
ok "已切换到本地分支 $(git branch --show-current)，与 origin/${BRANCH} 一致 · $(git rev-parse --short HEAD)"

# === 3. 依赖变动检测 + 后端 venv ===
AFTER_REQ=""
[ -f "${BACKEND_DIR}/requirements.txt" ] && AFTER_REQ=$(sha256sum "${BACKEND_DIR}/requirements.txt" | awk '{print $1}')

if [ ! -d "${VENV_DIR}" ]; then
    warn "未发现 venv ${VENV_DIR}；按运维指南步骤 5 创建"
    if ! command -v python3.11 >/dev/null 2>&1; then
        err "未找到 python3.11。Ubuntu 示例：sudo apt install -y python3.11 python3.11-venv"
        exit 1
    fi
    python3.11 -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install --upgrade pip
    "${VENV_DIR}/bin/pip" install -r "${BACKEND_DIR}/requirements.txt"
    ok "venv 已创建并安装依赖"
elif [ "${SYNC_FULL}" = "1" ]; then
    info "GCP_SYNC_FULL=1：全量 pip install -r requirements.txt"
    "${VENV_DIR}/bin/pip" install --upgrade pip
    "${VENV_DIR}/bin/pip" install -r "${BACKEND_DIR}/requirements.txt"
    ok "后端依赖已全量重装"
elif [ -n "${AFTER_REQ}" ] && [ "${BEFORE_REQ}" != "${AFTER_REQ}" ]; then
    info "检测到 backend/requirements.txt 变动，重装依赖"
    "${VENV_DIR}/bin/pip" install -r "${BACKEND_DIR}/requirements.txt"
    ok "后端依赖已更新"
else
    info "后端依赖无变动，跳过 pip install"
fi

# === 4. 依赖变动检测 + 前端构建 ===
AFTER_LOCK=""
[ -f "${FRONTEND_DIR}/package-lock.json" ] && AFTER_LOCK=$(sha256sum "${FRONTEND_DIR}/package-lock.json" | awk '{print $1}')

if [ ! -d "${FRONTEND_DIR}/node_modules" ]; then
    warn "未发现 frontend/node_modules；首次安装"
    (cd "${FRONTEND_DIR}" && npm ci)
    NEED_BUILD=1
elif [ "${SYNC_FULL}" = "1" ]; then
    info "GCP_SYNC_FULL=1：全量 npm ci"
    (cd "${FRONTEND_DIR}" && npm ci)
    NEED_BUILD=1
elif [ -n "${AFTER_LOCK}" ] && [ "${BEFORE_LOCK}" != "${AFTER_LOCK}" ]; then
    info "检测到 frontend/package-lock.json 变动，重装依赖"
    (cd "${FRONTEND_DIR}" && npm ci)
    NEED_BUILD=1
else
    NEED_BUILD=1
fi

if [ "${NEED_BUILD:-0}" = "1" ]; then
    info "前端构建中…"
    (cd "${FRONTEND_DIR}" && npm run build)
    ok "前端已构建到 ${FRONTEND_DIR}/dist"
fi

# 判断 systemd 是否已识别某单元（比 list-unit-files | grep 更稳：无 root 时列表可能不全、
# 或刚 cp 单元文件尚未 daemon-reload 导致「文件在磁盘但 list 里没有」）。
_gcp_backend_unit_ready() {
    local st
    st=$(systemctl show gcp-backend.service -p LoadState --value 2>/dev/null || true)
    if [ "$st" = "loaded" ]; then
        return 0
    fi
    if [ -f /etc/systemd/system/gcp-backend.service ]; then
        warn "已发现 /etc/systemd/system/gcp-backend.service，但 systemd 尚未加载；执行 daemon-reload…"
        sudo systemctl daemon-reload
        st=$(systemctl show gcp-backend.service -p LoadState --value 2>/dev/null || true)
        [ "$st" = "loaded" ] && return 0
    fi
    return 1
}

# === 5. 重启后端（必须）与本机健康检查 ===
if _gcp_backend_unit_ready; then
    info "重启 gcp-backend.service"
    sudo systemctl restart gcp-backend
    sleep 2
    if ! systemctl is-active --quiet gcp-backend; then
        err "gcp-backend 未处于 active 状态。请执行：sudo journalctl -u gcp-backend -n 80 --no-pager"
        exit 1
    fi
    ok "gcp-backend 已运行（systemd active）"

    info "本机健康检查：${LOCAL_HEALTH_URL}"
    if ! health_json=$(curl -fsS --max-time 20 "${LOCAL_HEALTH_URL}"); then
        err "无法连接本机 127.0.0.1:8000（uvicorn 是否监听？防火墙？）。请查看 journalctl。"
        exit 1
    fi
    if ! echo "${health_json}" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
        err "健康检查 JSON 中 ok 不为 true，后端可能启动异常。响应片段：${health_json:0:200}"
        exit 1
    fi
    ok "健康检查通过（确认新进程已加载并在响应 HTTP）"
    if ver_field=$(echo "${health_json}" | grep -oE '"version"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1); then
        [ -n "${ver_field}" ] && info "后端报告 ${ver_field}"
    fi

    info "OpenAPI 路由探测：${LOCAL_OPENAPI_URL}"
    if curl -fsS --max-time 15 "${LOCAL_OPENAPI_URL}" 2>/dev/null | grep -qE "scenario-packages|commit-intake|jobs/framework|jobs/world|jobs/.*/cancel|/runtime|/enter"; then
        ok "OpenAPI 已包含 scenario-packages（M1+ 路由已注册）"
    else
        info "OpenAPI 未出现 scenario-packages（main/M0 属正常；若你期望 M1+ 仍无此项，请核对分支与 commit）"
    fi
else
    err "systemd 未加载 gcp-backend.service（LoadState≠loaded）。请核对步骤 8 是否已执行，并在服务器上手动检查："
    err "  ls -la /etc/systemd/system/gcp-backend.service && systemctl show gcp-backend.service -p LoadState"
    err "  若文件存在但 LoadState=not-found：sudo systemctl daemon-reload && sudo systemctl enable --now gcp-backend"
    exit 1
fi

# === 6. reload Nginx ===
if systemctl show nginx.service -p LoadState --value 2>/dev/null | grep -qx loaded; then
    info "reload Nginx"
    sudo systemctl reload nginx
    ok "Nginx 已 reload"
else
    warn "未检测到 nginx.service，已跳过 reload（若你未装 Nginx 可忽略）"
fi

# === 7. 打印摘要 ===
COMMIT=$(git rev-parse --short HEAD)
BR_SHOW=$(git branch --show-current)
LOG1=$(git log -1 --oneline)
echo ""
ok "完成"
echo "    本地分支名 ：${BR_SHOW}（应与参数「${BRANCH}」一致）"
echo "    commit       ：${COMMIT}"
echo "    最近提交     ：${LOG1}"
echo "    手机浏览器   ：http://43.155.205.89"
echo "    调试页       ：http://43.155.205.89/debug/"
echo ""
info "若公网 API 仍异常，本机已验证 8000 端口；请再查 Nginx 反代与腾讯云安全组。"
