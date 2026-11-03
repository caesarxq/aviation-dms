import { lazy, Suspense } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { ToastProvider } from "./components/ui/Toast";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { getPostLoginPath } from "./auth/permissions";
import { RequireAccess, RequireAuth } from "./auth/RequireAccess";
import { LoginPage } from "./pages/Login";
import { PasswordSetupPage } from "./pages/PasswordSetup";
import ChangePasswordPage from "./pages/ChangePassword";
import { ForgotPasswordPage } from "./pages/ForgotPassword";
import { ResetPasswordPage } from "./pages/ResetPassword";
import { WelcomePage } from "./pages/Welcome";
import { ProfileSettingsPage } from "./pages/ProfileSettings";

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
const AuditTrail = lazy(() => import("./pages/AuditTrail").then((module) => ({ default: module.AuditTrail })));
const DocumentDistributions = lazy(() => import("./pages/DocumentDistributions").then((module) => ({ default: module.DocumentDistributions })));
const TrainingManagement = lazy(() => import("./pages/TrainingManagement").then((module) => ({ default: module.TrainingManagement })));
const MaintenanceManagement = lazy(() => import("./pages/MaintenanceManagement").then((module) => ({ default: module.MaintenanceManagement })));
const CrewManagement = lazy(() => import("./pages/CrewManagement").then((module) => ({ default: module.CrewManagement })));
const DutyTimeTracking = lazy(() => import("./pages/DutyTimeTracking").then((module) => ({ default: module.DutyTimeTracking })));
const CrewQualifications = lazy(() => import("./pages/CrewQualifications").then((module) => ({ default: module.CrewQualifications })));
const ChangeRequests = lazy(() => import("./pages/ChangeRequests").then((module) => ({ default: module.ChangeRequests })));
const SecurityManagement = lazy(() => import("./pages/SecurityManagement").then((module) => ({ default: module.SecurityManagement })));
const OutsourcedFunctions = lazy(() => import("./pages/P2Pages").then((module) => ({ default: module.OutsourcedFunctions })));
const SafetyKPIs = lazy(() => import("./pages/P2Pages").then((module) => ({ default: module.SafetyKPIs })));
const SecurityReviews = lazy(() => import("./pages/P2Pages").then((module) => ({ default: module.SecurityReviews })));
const DGResponsibilityMatrix = lazy(() => import("./pages/P2Pages").then((module) => ({ default: module.DGResponsibilityMatrix })));
const AuditReports = lazy(() => import("./pages/AuditReports").then((module) => ({ default: module.AuditReports })));
const AuditFindings = lazy(() => import("./pages/AuditFindings").then((module) => ({ default: module.AuditFindings })));
const AuditDashboard = lazy(() => import("./pages/AuditDashboard").then((module) => ({ default: module.AuditDashboard })));
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

function AuthenticatedRouteFallback() {
  const { profile } = useAuth();
  return <Navigate to={getPostLoginPath(profile)} replace />;
}

function OnboardingGate({ children }: { children: React.ReactNode }) {
  const { profile } = useAuth();
  const location = useLocation();
  // Allow access to /welcome when onboarding is incomplete; redirect away when complete.
  if (location.pathname === "/welcome") {
    if (profile?.onboarding_completed) {
      return <Navigate to={getPostLoginPath(profile)} replace />;
    }
    return children;
  }
  if (!profile || profile.onboarding_completed) return children;
  return <Navigate to="/welcome" replace />;
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <Suspense fallback={<RouteLoading />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/setup" element={<PasswordSetupPage />} />
            <Route path="/setup/invite/:code" element={<PasswordSetupPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password/:token" element={<ResetPasswordPage />} />
            <Route element={<RequireAuth><OnboardingGate><AppShell /></OnboardingGate></RequireAuth>}>
              <Route path="/welcome" element={<WelcomePage />} />
              <Route path="/" element={<RequireAccess permission="safety:read"><Dashboard /></RequireAccess>} />
              <Route path="/documents" element={<RequireAccess anyPermissions={["document:read", "document:propose"]}><DocumentCatalogue /></RequireAccess>} />
              <Route path="/occurrences" element={<RequireAccess permission="safety:read"><Occurrences /></RequireAccess>} />
              <Route path="/occurrences/:occurrenceId" element={<RequireAccess permission="safety:read"><OccurrenceDetail /></RequireAccess>} />
              <Route path="/roc" element={<RequireAccess permission="roc:read"><ROCRegister /></RequireAccess>} />
              <Route path="/missions" element={<RequireAccess permission="safety:read"><Missions /></RequireAccess>} />
              <Route path="/quality-audits" element={<RequireAccess permission="safety:read"><QualityAudits /></RequireAccess>} />
              <Route path="/corrective-actions" element={<RequireAccess permission="safety:read"><CorrectiveActions /></RequireAccess>} />
              <Route path="/dangerous-goods" element={<RequireAccess permission="safety:read"><DangerousGoods /></RequireAccess>} />
              <Route path="/hazards" element={<RequireAccess permission="safety:read"><Hazards /></RequireAccess>} />
              <Route path="/risk-assessments" element={<RequireAccess permission="safety:read"><RiskAssessments /></RequireAccess>} />
              <Route path="/investigations" element={<RequireAccess permission="safety:read"><Investigations /></RequireAccess>} />
              <Route path="/safety-actions" element={<RequireAccess permission="safety:read"><SafetyActions /></RequireAccess>} />
              <Route path="/audit-trail" element={<RequireAccess permission="audit:read"><AuditTrail /></RequireAccess>} />
              <Route path="/distributions" element={<RequireAccess permission="document:read"><DocumentDistributions /></RequireAccess>} />
              <Route path="/training" element={<RequireAccess permission="personnel:read"><TrainingManagement /></RequireAccess>} />
              <Route path="/maintenance" element={<RequireAccess permission="aircraft:read"><MaintenanceManagement /></RequireAccess>} />
              <Route path="/crew" element={<RequireAccess permission="personnel:read"><CrewManagement /></RequireAccess>} />
              <Route path="/duties" element={<RequireAccess permission="personnel:read"><DutyTimeTracking /></RequireAccess>} />
              <Route path="/crew-qualifications" element={<RequireAccess permission="personnel:read"><CrewQualifications /></RequireAccess>} />
              <Route path="/change-requests" element={<RequireAccess permission="document:read"><ChangeRequests /></RequireAccess>} />
              <Route path="/security" element={<RequireAccess permission="security:read_sensitive"><SecurityManagement /></RequireAccess>} />
              <Route path="/outsourced-functions" element={<RequireAccess permission="compliance:read"><OutsourcedFunctions /></RequireAccess>} />
              <Route path="/safety-kpis" element={<RequireAccess permission="safety:read"><SafetyKPIs /></RequireAccess>} />
              <Route path="/security-reviews" element={<RequireAccess permission="security:read_sensitive"><SecurityReviews /></RequireAccess>} />
              <Route path="/dg-responsibility-matrix" element={<RequireAccess permission="safety:read"><DGResponsibilityMatrix /></RequireAccess>} />
              <Route path="/documents/:docId/edit" element={<RequireAccess anyPermissions={["document:update", "document:propose"]}><DocumentEditor /></RequireAccess>} />
              <Route path="/documents/:docId/view" element={<RequireAccess anyPermissions={["document:read", "document:propose", "document:update"]}><DocumentViewer /></RequireAccess>} />
              <Route path="/personnel-licenses" element={<RequireAccess permission="personnel:read"><PersonnelLicenses /></RequireAccess>} />
              <Route path="/self-service-upload" element={<RequireAccess permission="personnel:view"><SelfServiceUpload /></RequireAccess>} />
              <Route path="/document-proposals" element={<RequireAccess anyPermissions={["document:read", "document:propose"]}><DocumentProposals /></RequireAccess>} />
              <Route path="/renewal-progress" element={<RequireAccess permission="personnel:read"><RenewalProgress /></RequireAccess>} />
              <Route path="/version-diff" element={<RequireAccess permission="document:read"><VersionDiff /></RequireAccess>} />
              <Route path="/aircraft-insurance" element={<RequireAccess permission="aircraft:read"><AircraftInsurance /></RequireAccess>} />
              <Route path="/admin/observability" element={<RequireAccess role="system_admin"><AdminObservability /></RequireAccess>} />
              <Route path="/audit-reports" element={<RequireAccess permission="audit_report:read"><AuditReports /></RequireAccess>} />
              <Route path="/audit-findings" element={<RequireAccess permission="audit_finding:read"><AuditFindings /></RequireAccess>} />
              <Route path="/audit-findings/:findingId" element={<RequireAccess permission="audit_finding:read"><AuditFindings /></RequireAccess>} />
              <Route path="/audit-dashboard" element={<RequireAccess permission="audit_finding:read"><AuditDashboard /></RequireAccess>} />
              <Route path="/notifications" element={<RequireAccess permission="safety:read"><Notifications /></RequireAccess>} />
              <Route path="/account/security" element={<ChangePasswordPage />} />
              <Route path="/account/profile" element={<ProfileSettingsPage />} />
              <Route path="*" element={<AuthenticatedRouteFallback />} />
            </Route>
          </Routes>
        </Suspense>
      </AuthProvider>
    </ToastProvider>
  );
}
