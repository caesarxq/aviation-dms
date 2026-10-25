import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { ToastProvider } from "./components/ui/Toast";

const Dashboard = lazy(() => import("./pages/Dashboard").then((module) => ({ default: module.Dashboard })));
const DocumentCatalogue = lazy(() => import("./pages/DocumentCatalogue").then((module) => ({ default: module.DocumentCatalogue })));
const Occurrences = lazy(() => import("./pages/Occurrences").then((module) => ({ default: module.Occurrences })));
const OccurrenceDetail = lazy(() => import("./pages/OccurrenceDetail").then((module) => ({ default: module.OccurrenceDetail })));
const ROCRegister = lazy(() => import("./pages/ROCRegister").then((module) => ({ default: module.ROCRegister })));
const Missions = lazy(() => import("./pages/Missions").then((module) => ({ default: module.Missions })));
const QualityAudits = lazy(() => import("./pages/QualityAudits").then((module) => ({ default: module.QualityAudits })));
const CorrectiveActions = lazy(() => import("./pages/QualityAudits").then((module) => ({ default: module.CorrectiveActions })));
const DangerousGoods = lazy(() => import("./pages/DangerousGoods").then((module) => ({ default: module.DangerousGoods })));
const Hazards = lazy(() => import("./pages/Hazards").then((module) => ({ default: module.Hazards })));
const RiskAssessments = lazy(() => import("./pages/RiskAssessments").then((module) => ({ default: module.RiskAssessments })));
const Investigations = lazy(() => import("./pages/Investigations").then((module) => ({ default: module.Investigations })));
const SafetyActions = lazy(() => import("./pages/SafetyActions").then((module) => ({ default: module.SafetyActions })));
const SecurityManagement = lazy(() => import("./pages/SecurityManagement").then((module) => ({ default: module.SecurityManagement })));
const OutsourcedFunctions = lazy(() => import("./pages/P2Pages").then((module) => ({ default: module.OutsourcedFunctions })));
const SafetyKPIs = lazy(() => import("./pages/P2Pages").then((module) => ({ default: module.SafetyKPIs })));
const SecurityReviews = lazy(() => import("./pages/P2Pages").then((module) => ({ default: module.SecurityReviews })));
const DGResponsibilityMatrix = lazy(() => import("./pages/P2Pages").then((module) => ({ default: module.DGResponsibilityMatrix })));
const DocumentEditor = lazy(() => import("./pages/DocumentEditor").then((module) => ({ default: module.DocumentEditor })));
const DocumentViewer = lazy(() => import("./pages/DocumentViewer").then((module) => ({ default: module.DocumentViewer })));
const Notifications = lazy(() => import("./pages/Notifications").then((module) => ({ default: module.Notifications })));
const PersonnelLicenses = lazy(() => import("./pages/PersonnelLicenses"));
const DocumentProposals = lazy(() => import("./pages/DocumentProposals"));
const RenewalProgress = lazy(() => import("./pages/RenewalProgress"));
const VersionDiff = lazy(() => import("./pages/VersionDiff"));
const SelfServiceUpload = lazy(() => import("./pages/SelfServiceUpload"));
const AircraftInsurance = lazy(() => import("./pages/AircraftInsurance"));
const AdminObservability = lazy(() => import("./pages/AdminObservability"));

function RouteLoading() {
  return <div className="app-surface p-10 text-center text-sm text-kfl-muted">Loading page…</div>;
}

export default function App() {
  return (
    <ToastProvider>
      <Suspense fallback={<RouteLoading />}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/documents" element={<DocumentCatalogue />} />
            <Route path="/occurrences" element={<Occurrences />} />
            <Route path="/occurrences/:occurrenceId" element={<OccurrenceDetail />} />
            <Route path="/roc" element={<ROCRegister />} />
            <Route path="/missions" element={<Missions />} />
            <Route path="/quality-audits" element={<QualityAudits />} />
            <Route path="/corrective-actions" element={<CorrectiveActions />} />
            <Route path="/dangerous-goods" element={<DangerousGoods />} />
            <Route path="/hazards" element={<Hazards />} />
            <Route path="/risk-assessments" element={<RiskAssessments />} />
            <Route path="/investigations" element={<Investigations />} />
            <Route path="/safety-actions" element={<SafetyActions />} />
            <Route path="/security" element={<SecurityManagement />} />
            <Route path="/outsourced-functions" element={<OutsourcedFunctions />} />
            <Route path="/safety-kpis" element={<SafetyKPIs />} />
            <Route path="/security-reviews" element={<SecurityReviews />} />
            <Route path="/dg-responsibility-matrix" element={<DGResponsibilityMatrix />} />
            <Route path="/documents/:docId/edit" element={<DocumentEditor />} />
            <Route path="/documents/:docId/view" element={<DocumentViewer />} />
            <Route path="/personnel-licenses" element={<PersonnelLicenses />} />
            <Route path="/self-service-upload" element={<SelfServiceUpload />} />
            <Route path="/document-proposals" element={<DocumentProposals />} />
            <Route path="/renewal-progress" element={<RenewalProgress />} />
            <Route path="/version-diff" element={<VersionDiff />} />
            <Route path="/aircraft-insurance" element={<AircraftInsurance />} />
            <Route path="/admin/observability" element={<AdminObservability />} />
            <Route path="/notifications" element={<Notifications />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </ToastProvider>
  );
}
