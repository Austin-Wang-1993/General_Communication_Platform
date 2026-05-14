import { Routes, Route, Navigate } from 'react-router-dom';

import { WelcomePage } from './pages/WelcomePage';

/**
 * 路由表（与 docs/engineering/01-技术方案.md §10 一致）。
 * M0 阶段：仅装配欢迎页 + 健康检查；M6+ 起填充剩余页面。
 */
function App() {
  return (
    <Routes>
      <Route path="/" element={<WelcomePage />} />
      {/* M6+ 路由占位：
          /scenarios                       → P2
          /scenarios/new                   → P2.1
          /scenarios/new/framework-loading → P2.2
          /scenarios/new/framework         → P2.3
          /scenarios/new/world-loading     → P2.4
          /scenarios/new/world             → P2.5
          /scenarios/:id/chat              → P3 (含 P3a 弹窗)
          /debug                           → 跳转到后端 /debug/
      */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
