import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from './components/ui/Toast';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';

// Lazy-loaded pages: split bundles by route.
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const TaskFrontDoorPage = lazy(() => import('./pages/TaskFrontDoorPage'));
const TaskResultPage = lazy(() => import('./pages/TaskResultPage'));
const LegionPage = lazy(() => import('./pages/LegionPage'));
const OrchestratorPage = lazy(() => import('./pages/OrchestratorPage'));
const PrototypeAgentsPage = lazy(() => import('./pages/PrototypeAgentsPage'));
const HistoryPage = lazy(() => import('./pages/HistoryPage'));

const BatchPage = lazy(() => import('./pages/BatchPage'));
const PerformancePage = lazy(() => import('./pages/PerformancePage'));
const SecurityPage = lazy(() => import('./pages/SecurityPage'));
const ApiPage = lazy(() => import('./pages/ApiPage'));
const DatabasePage = lazy(() => import('./pages/DatabasePage'));
const QualityPage = lazy(() => import('./pages/QualityPage'));
const ResiliencePage = lazy(() => import('./pages/ResiliencePage'));
const KnowledgePage = lazy(() => import('./pages/KnowledgePage'));
const CICDPage = lazy(() => import('./pages/CICDPage'));
const RequirementPage = lazy(() => import('./pages/RequirementPage'));
const ExploratoryPage = lazy(() => import('./pages/ExploratoryPage'));
const ContractPage = lazy(() => import('./pages/ContractPage'));
const MobilePage = lazy(() => import('./pages/MobilePage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const EvaluationPage = lazy(() => import('./pages/EvaluationPage'));
const SemanticTestPage = lazy(() => import('./pages/SemanticTestPage'));
const QualityGatePage = lazy(() => import('./pages/QualityGatePage'));

const NotificationPage = lazy(() => import('./pages/NotificationPage'));
const SchedulerPage = lazy(() => import('./pages/SchedulerPage'));
const TestDataPage = lazy(() => import('./pages/TestDataPage'));
const ScenarioPage = lazy(() => import('./pages/ScenarioPage'));
const VisualPage = lazy(() => import('./pages/VisualPage'));
const DeployPage = lazy(() => import('./pages/DeployPage'));

function PageLoader() {
    return (
        <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
        </div>
    );
}

/* PageErrorBoundary and Suspense isolate page failures.*/
function SafePage({ children }: { children: React.ReactNode }) {
    return (
        <ErrorBoundary>
            <Suspense fallback={<PageLoader />}>
                {children}
            </Suspense>
        </ErrorBoundary>
    );
}

function App() {
    return (
        <ToastProvider>
            <BrowserRouter>
                <Routes>
                    <Route element={<Layout />}>
                        <Route index element={<SafePage><TaskFrontDoorPage /></SafePage>} />
                        <Route path="tasks/:taskId" element={<SafePage><TaskResultPage /></SafePage>} />
                        <Route path="dashboard" element={<SafePage><DashboardPage /></SafePage>} />
                        <Route path="legion" element={<SafePage><LegionPage /></SafePage>} />
                        <Route path="orchestrator" element={<SafePage><OrchestratorPage /></SafePage>} />
                        <Route path="prototype-agents" element={<SafePage><PrototypeAgentsPage /></SafePage>} />
                        <Route path="history" element={<SafePage><HistoryPage /></SafePage>} />
                        <Route path="gallery" element={<Navigate to="/history" replace />} />
                        <Route path="api-workbench" element={<SafePage><ApiPage /></SafePage>} />
                        <Route path="database" element={<SafePage><DatabasePage /></SafePage>} />
                        <Route path="performance" element={<SafePage><PerformancePage /></SafePage>} />
                        <Route path="security" element={<SafePage><SecurityPage /></SafePage>} />
                        <Route path="knowledge" element={<SafePage><KnowledgePage /></SafePage>} />
                        <Route path="settings" element={<SafePage><SettingsPage /></SafePage>} />
                        {/* Redirect legacy routes.*/}
                        <Route path="commander" element={<Navigate to="/legion" replace />} />
                        <Route path="warroom" element={<Navigate to="/legion" replace />} />
                        <Route path="batch" element={<SafePage><BatchPage /></SafePage>} />
                        <Route path="quality" element={<SafePage><QualityPage /></SafePage>} />
                        <Route path="resilience" element={<SafePage><ResiliencePage /></SafePage>} />
                        <Route path="cicd" element={<SafePage><CICDPage /></SafePage>} />
                        <Route path="requirement" element={<SafePage><RequirementPage /></SafePage>} />
                        <Route path="exploratory" element={<SafePage><ExploratoryPage /></SafePage>} />
                        <Route path="contract" element={<SafePage><ContractPage /></SafePage>} />
                        <Route path="i18n-a11y" element={<Navigate to="/quality" replace />} />
                        <Route path="mobile" element={<SafePage><MobilePage /></SafePage>} />
                        <Route path="evaluation" element={<SafePage><EvaluationPage /></SafePage>} />
                        <Route path="semantic" element={<SafePage><SemanticTestPage /></SafePage>} />
                        <Route path="quality-gate" element={<SafePage><QualityGatePage /></SafePage>} />
                        <Route path="reports" element={<Navigate to="/history" replace />} />
                        <Route path="notifications" element={<SafePage><NotificationPage /></SafePage>} />
                        <Route path="scheduler" element={<SafePage><SchedulerPage /></SafePage>} />
                        <Route path="testdata" element={<SafePage><TestDataPage /></SafePage>} />
                        <Route path="scenario" element={<SafePage><ScenarioPage /></SafePage>} />
                        <Route path="visual" element={<SafePage><VisualPage /></SafePage>} />
                        <Route path="deploy" element={<SafePage><DeployPage /></SafePage>} />
                        <Route path="*" element={<Navigate to="/" replace />} />
                    </Route>
                </Routes>
            </BrowserRouter>
        </ToastProvider>
    );
}

export default App;
