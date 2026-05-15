import { Routes, Route, Navigate } from 'react-router-dom';

import { ChatPlaceholderPage } from './pages/ChatPlaceholderPage';
import { IntakeWizardPage } from './pages/IntakeWizardPage';
import { JobWaitPage } from './pages/JobWaitPage';
import { ScenariosPage } from './pages/ScenariosPage';
import { WelcomePage } from './pages/WelcomePage';

/**
 * 路由表（前端需求文档 §1 + 技术方案 §9 M6）。
 */
function App() {
  return (
    <Routes>
      <Route path="/" element={<WelcomePage />} />
      <Route path="/scenarios" element={<ScenariosPage />} />
      <Route path="/scenarios/:scenarioId/setup" element={<IntakeWizardPage />} />
      <Route path="/scenarios/:scenarioId/jobs/:jobId/:jobKind" element={<JobWaitPage />} />
      <Route path="/scenarios/:scenarioId/chat" element={<ChatPlaceholderPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
