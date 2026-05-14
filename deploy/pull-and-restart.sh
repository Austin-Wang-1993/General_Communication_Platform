#!/usr/bin/env bash
# 通用英语对话练习 · 拉取并重启脚本
#
# 用法：
#   ./deploy/pull-and-restart.sh                      # 拉 main 分支并重启
#   ./deploy/pull-and-restart.sh cursor/m0-skeleton-a4d3  # 拉指定 feature 分支并重启
#
# 设计与 docs/engineering/01-技术方案.md §11.2 双分支测试-合并工作流对齐：
#   - 不传参数 = 拉 main 作为已验收基线
#   - 传 feature 分支名 = 拉该分支用于测试
#
# 内部步骤：
#   1) git fetch origin <branch>
#   2) git reset --hard origin/<branch>（弃用本地修改，确保与远端一致）
#   3) 若 backend/requirements.txt 变动则 pip install -r
#   4) 若 frontend/package-lock.json 变动则 npm ci && npm run build
#   5) sudo systemctl restart gcp-backend
#   6) sudo systemctl reload nginx
#   7) 打印当前 commit 短哈希与分支名

set -euo pipefail

BRANCH="${1:-main}"
REPO_DIR="${GCP_REPO_DIR:-/opt/gcp}"
BACKEND_DIR="${REPO_DIR}/backend"
FRONTEND_DIR="${REPO_DIR}/frontend"
VENV_DIR="${BACKEND_DIR}/.venv"

color() {
    local code="$1"; shift
    printf "\033[%sm%s\033[0m\n" "$code" "$*"
}
info()  { color "1;36" "[$(date +%T)] $*"; }
ok()    { color "1;32" "[$(date +%T)] ✓ $*"; }
warn()  { color "1;33" "[$(date +%T)] ⚠ $*"; }
err()   { color "1;31" "[$(date +%T)] ✗ $*"; }

cd "$REPO_DIR"

# === 1. 记录变动前的依赖文件 hash ===
BEFORE_REQ=""
BEFORE_LOCK=""
[ -f "${BACKEND_DIR}/requirements.txt" ] && BEFORE_REQ=$(sha256sum "${BACKEND_DIR}/requirements.txt" | awk '{print $1}')
[ -f "${FRONTEND_DIR}/package-lock.json" ] && BEFORE_LOCK=$(sha256sum "${FRONTEND_DIR}/package-lock.json" | awk '{print $1}')

# === 2. 拉取目标分支 ===
info "拉取分支：${BRANCH}"
git fetch origin "${BRANCH}"
git reset --hard "origin/${BRANCH}"
ok "代码已对齐 origin/${BRANCH}"

# === 3. 依赖变动检测 + 后端 ===
AFTER_REQ=""
[ -f "${BACKEND_DIR}/requirements.txt" ] && AFTER_REQ=$(sha256sum "${BACKEND_DIR}/requirements.txt" | awk '{print $1}')

if [ ! -d "${VENV_DIR}" ]; then
    warn "未发现 venv ${VENV_DIR}；按 §11.1 步骤 5 创建"
    python3.11 -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install --upgrade pip
    "${VENV_DIR}/bin/pip" install -r "${BACKEND_DIR}/requirements.txt"
    ok "venv 已创建并安装依赖"
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
elif [ -n "${AFTER_LOCK}" ] && [ "${BEFORE_LOCK}" != "${AFTER_LOCK}" ]; then
    info "检测到 frontend/package-lock.json 变动，重装依赖"
    (cd "${FRONTEND_DIR}" && npm ci)
    NEED_BUILD=1
else
    NEED_BUILD=1   # M0 阶段每次都重新 build，确保 dist 与代码一致；后续可加 hash 跳过
fi

if [ "${NEED_BUILD:-0}" = "1" ]; then
    info "前端构建中…"
    (cd "${FRONTEND_DIR}" && npm run build)
    ok "前端已构建到 ${FRONTEND_DIR}/dist"
fi

# === 5. 重启后端与 reload Nginx ===
if systemctl list-unit-files | grep -q '^gcp-backend.service'; then
    info "重启 gcp-backend.service"
    sudo systemctl restart gcp-backend
    sleep 1
    if systemctl is-active --quiet gcp-backend; then
        ok "gcp-backend 已运行"
        # 自检：M1+ 应在 OpenAPI 中出现 scenario-packages；若缺失多为仍跑旧代码或未 reload 进程
        if curl -fsS --max-time 5 "http://127.0.0.1:8000/openapi.json" 2>/dev/null | grep -q "scenario-packages"; then
            ok "OpenAPI 已包含 scenario-packages（M1 路由已加载）"
        else
            warn "OpenAPI 中未找到 scenario-packages — 若你期望 M1，请核对：① git 是否在含 M1 的分支 ② journalctl -u gcp-backend 是否有 ImportError"
        fi
    else
        err "gcp-backend 启动失败！查看：sudo journalctl -u gcp-backend -n 50"
        exit 1
    fi
else
    warn "未注册 gcp-backend.service（首次部署？）参见 §11.1 步骤 8"
fi

if systemctl list-unit-files | grep -q '^nginx.service'; then
    info "reload Nginx"
    sudo systemctl reload nginx
    ok "Nginx 已 reload"
else
    warn "未安装 Nginx？参见 §11.1 步骤 2"
fi

# === 6. 打印当前状态 ===
COMMIT=$(git rev-parse --short HEAD)
echo ""
ok "完成 · 当前分支：${BRANCH} · commit：${COMMIT}"
echo "    手机浏览器打开：http://43.155.205.89"
echo "    调试页：       http://43.155.205.89/debug/"
