import { Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { Dashboard } from "./pages/Dashboard";
import { DocumentCatalogue } from "./pages/DocumentCatalogue";
import { Occurrences } from "./pages/Occurrences";
import { OccurrenceDetail } from "./pages/OccurrenceDetail";
import { ROCRegister } from "./pages/ROCRegister";
import { Missions } from "./pages/Missions";
import { QualityAudits, CorrectiveActions } from "./pages/QualityAudits";
import { DangerousGoods } from "./pages/DangerousGoods";
import { SecurityManagement } from "./pages/SecurityManagement";
import { OutsourcedFunctions, SafetyKPIs, SecurityReviews, DGResponsibilityMatrix } from "./pages/P2Pages";
import { DocumentEditor } from "./pages/DocumentEditor";
import { DocumentViewer } from "./pages/DocumentViewer";
import { Notifications } from "./pages/Notifications";

export default function App() {
  return (
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
        <Route path="/security" element={<SecurityManagement />} />
        <Route path="/outsourced-functions" element={<OutsourcedFunctions />} />
        <Route path="/safety-kpis" element={<SafetyKPIs />} />
        <Route path="/security-reviews" element={<SecurityReviews />} />
        <Route path="/dg-responsibility-matrix" element={<DGResponsibilityMatrix />} />
        <Route path="/documents/:docId/edit" element={<DocumentEditor />} />
        <Route path="/documents/:docId/view" element={<DocumentViewer />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
