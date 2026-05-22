# 场景对话页线框 · 402×874

## 文件

- **`index.html`**：单文件线框，画布固定 **402px × 874px**，便于墨刀「HTML 转原型」导入。

## 结构说明（与 HTML 内 `id` 对应）

| 区域 | `id` / 说明 |
|------|-------------|
| A 顶栏 | `#region-header`；`#btn-back-catalog`、`#block-scenario-title`、`#block-header-actions` 及右侧各按钮 |
| B 目标进度 | `#region-progress`；`#widget-progress-bar`、`#text-progress-percent` |
| C 聊天主区 | `#region-chat`；`#row-msg-npc-*` / `#row-msg-user-*`，NPC 气泡旁 `#btn-trans-npc-*`（翻） |
| D 底栏 | `#region-footer`；`#input-message-placeholder`、`#btn-select-speaker`、`#btn-send` |

## 导入墨刀

1. 在墨刀中选择通过 **HTML 生成页面 / 导入 HTML**（以墨刀当前版本菜单为准）。  
2. 选择本目录下的 **`index.html`**。  
3. 导入后可将灰色 **「区域 X · …」** 标签图层隐藏或删除，仅保留线框组件。

## 标注

- 按钮右上角 **⚡** 表示线框阶段「待产品或交互细化」，可按需删除。
