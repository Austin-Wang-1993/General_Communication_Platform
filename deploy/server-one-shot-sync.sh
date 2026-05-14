#!/usr/bin/env bash
# 服务器「一键同步」入口：先对齐 main 上的部署脚本，再部署指定远端分支。
#
# 给非技术用户用：由 Agent 告诉你整段复制命令（见 docs/operations/01-腾讯云部署指南.md）。
#
# 用法：
#   bash deploy/server-one-shot-sync.sh main
#   bash deploy/server-one-shot-sync.sh cursor/某-feature-分支
#
# 环境变量（可选）：
#   GCP_REPO_DIR   仓库根路径，默认 /opt/gcp
#   GCP_SYNC_FULL  默认已设为 1（全量 pip + npm ci，更慢更稳）；设为 0 可恢复「按需安装」

set -euo pipefail

TARGET_BRANCH="${1:?缺少参数：请传入要部署的远端分支名。示例: bash deploy/server-one-shot-sync.sh main}"

REPO_DIR="${GCP_REPO_DIR:-/opt/gcp}"
if [ ! -f "${REPO_DIR}/deploy/pull-and-restart.sh" ]; then
    echo "错误：未找到 ${REPO_DIR}/deploy/pull-and-restart.sh（GCP_REPO_DIR 是否正确？当前在 $(pwd)）" >&2
    exit 1
fi

cd "$REPO_DIR"

# 默认全量同步（依赖重装 + npm ci），可通过 GCP_SYNC_FULL=0 关闭
export GCP_SYNC_FULL="${GCP_SYNC_FULL:-1}"

# 先拉取 main 并把工作区指到 main，确保本脚本与 pull-and-restart 为远端最新版
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "错误：${REPO_DIR} 不是 git 仓库" >&2
    exit 1
fi

git fetch origin main "${TARGET_BRANCH}" 2>/dev/null || git fetch origin main
git checkout main
git reset --hard origin/main

exec bash "${REPO_DIR}/deploy/pull-and-restart.sh" "${TARGET_BRANCH}"
