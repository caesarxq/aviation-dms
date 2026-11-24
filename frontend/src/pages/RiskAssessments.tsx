import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { CheckCircle, ShieldCheck, Plus, Download, UserCheck } from "lucide-react";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useToast } from "../components/ui/Toast";
import { useAuth } from "../auth/AuthContext";
import type { RiskAssessment } from "../types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

function riskModelLabel(model: string): string {
  return model === "om_flight_26" ? "OM §2.6" : "SMS 5×5";
}

export function RiskAssessments() {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const { toast } = useToast();
  const canCreate = hasPermission("safety:create");
  const canApprove = hasPermission("risk_assessment:approve");
  const pageSize = 50;
  const [statusFilter, setStatusFilter] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
  const [page, setPage] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [hazardIds, setHazardIds] = useState<string[]>([]);
  const [newHazardId, setNewHazardId] = useState("");
  const [occurrenceId, setOccurrenceId] = useState("");
  const [missionId, setMissionId] = useState("");
  const [missionSearch, setMissionSearch] = useState("");
  const [riskModel, setRiskModel] = useState("sms_5x5");
  const [likelihood, setLikelihood] = useState("possible");
  const [severity, setSeverity] = useState("minor");
  const [riskLevel, setRiskLevel] = useState("medium");
  const [exposure, setExposure] = useState("possible");
  const [mitigationMeasures, setMitigationMeasures] = useState("");
  const [residualRisk, setResidualRisk] = useState("");
  const [dirty, setDirty] = useState(false);
  const [createError, setCreateError] = useState("");
  const [actionError, setActionError] = useState("");
  const [lastCreated, setLastCreated] = useState<RiskAssessment | null>(null);

  // PDF-aligned fields matching KFL Drone Risk Assessment template
  const [picFullName, setPicFullName] = useState("");
  const [locationCoordinates, setLocationCoordinates] = useState("");
  const [droneTypeModel, setDroneTypeModel] = useState("");
  const [projectType, setProjectType] = useState("");
  const [flightDecision, setFlightDecision] = useState("");
  const [conditionsNotes, setConditionsNotes] = useState("");
  const [headOfSafetyName, setHeadOfSafetyName] = useState("");
  const [safetySignature, setSafetySignature] = useState("");
  const [approvalDate, setApprovalDate] = useState("");
  const [assessmentDate, setAssessmentDate] = useState("");

  const KFL_HAZARDS = [
    { id: "trees", name: "Trees", risk: "Collision with canopy or branches.", mitigation: "Survey canopy height and maintain clearance along the route.", score: "6 Medium", ls: "L2 × S3" },
    { id: "buildings", name: "Buildings", risk: "Collision with structures or roof obstacles.", mitigation: "Survey the route and set a buffer from structures.", score: "6 Medium", ls: "L2 × S3" },
    { id: "human_traffic", name: "Human traffic", risk: "Injury to people in the flight area.", mitigation: "Control access. Pause or land if people enter the flight area.", score: "4 Low", ls: "L1 × S4" },
    { id: "wildlife", name: "Wildlife", risk: "Animal disturbance or bird strike.", mitigation: "Maintain separation. Stop if wildlife approaches or shows distress.", score: "3 Low", ls: "L1 × S3" },
    { id: "manned_aircraft", name: "Manned aircraft", risk: "Mid-air collision.", mitigation: "Check airspace, scan for traffic and yield immediately to crewed aircraft.", score: "5 Medium", ls: "L1 × S5" },
    { id: "strong_winds", name: "Strong winds", risk: "Loss of control or inability to return.", mitigation: "Check gusts and return margin. Hold if wind exceeds operating limits.", score: "6 Medium", ls: "L2 × S3" },
    { id: "communication_towers", name: "Communication towers", risk: "Collision with towers or guy wires.", mitigation: "Locate towers and guy wires. Keep the flight path clear of both.", score: "4 Low", ls: "L1 × S4" },
    { id: "electric_poles", name: "Electric poles / power lines", risk: "Wire strike or electrical contact.", mitigation: "Identify poles and spans. Set a safe stand-off distance.", score: "4 Low", ls: "L1 × S4" },
  ];
  const [selectedHazards, setSelectedHazards] = useState<Record<string, boolean>>({});

  const { data: fetchedAssessments = [], isLoading, isError, error, refetch } = useQuery<RiskAssessment[]>({
    queryKey: ["risk-assessments", statusFilter, riskFilter, page],
    queryFn: () => safetyApi.listRiskAssessments({
      ...(statusFilter ? { status: statusFilter } : {}),
      ...(riskFilter ? { risk_level: riskFilter } : {}),
      limit: pageSize + 1,
      offset: page * pageSize,
    }),
  });
  const hasNextPage = fetchedAssessments.length > pageSize;
  const assessments = fetchedAssessments.slice(0, pageSize);
  const {
    data: summary,
    isLoading: summaryLoading,
    isError: summaryError,
    refetch: refetchSummary,
  } = useQuery({
    queryKey: ["risk-assessments-summary"],
    queryFn: () => safetyApi.getRiskAssessmentSummary(),
  });
  const { data: plannedMissions = [], isError: missionsError } = useQuery({
    queryKey: ["risk-assessment-planned-missions", missionSearch],
    queryFn: () => safetyApi.listMissions({
      status: "planned",
      ...(missionSearch.trim() ? { search: missionSearch.trim() } : {}),
      limit: 100,
      offset: 0,
    }),
    enabled: showForm,
  });

  const addHazard = () => {
    const hid = newHazardId.trim();
    if (!hid || hazardIds.includes(hid)) return;
    setHazardIds([...hazardIds, hid]);
    setNewHazardId("");
    setDirty(true);
  };

  const removeHazard = (idToRemove: string) => {
    setHazardIds(hazardIds.filter((id) => id !== idToRemove));
    setDirty(true);
  };

  const { errors: raErrors, isValid: raIsValid } = useValidation(
    {
      title,
      description,
      likelihood,
      severity,
      pic_full_name: picFullName,
      location_coordinates: locationCoordinates,
      drone_type_model: droneTypeModel,
      project_type: projectType,
      flight_decision: flightDecision,
      risk_level: riskModel === "sms_5x5" ? riskLevel : "not_applicable",
      exposure: riskModel === "om_flight_26" ? exposure : "not_applicable",
    },
    {
      title: { required: true, minLength: 2 },
      description: { required: true, minLength: 5 },
      likelihood: { required: true },
      severity: { required: true },
      pic_full_name: { required: true, minLength: 2 },
      location_coordinates: { required: true },
      drone_type_model: { required: true },
      project_type: { required: true },
      flight_decision: { required: true },
      ...(riskModel === "sms_5x5" ? { risk_level: { required: true } } : { exposure: { required: true } }),
    }
  );

  useUnsavedChanges(showForm && dirty);

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => safetyApi.createRiskAssessment(data),
    onSuccess: (created: RiskAssessment) => {
      qc.invalidateQueries({ queryKey: ["risk-assessments"] });
      qc.invalidateQueries({ queryKey: ["risk-assessments-summary"] });
      setLastCreated(created);
      setCreateError("");
      setShowForm(false);
      setDirty(false);
      setTitle("");
      setDescription("");
      setHazardIds([]);
      setNewHazardId("");
      setOccurrenceId("");
      setMissionId("");
      setRiskModel("sms_5x5");
      setLikelihood("possible");
      setSeverity("minor");
      setRiskLevel("medium");
      setExposure("possible");
      setMitigationMeasures("");
      setResidualRisk("");
      toast({ title: "Risk assessment recorded", message: "The server-calculated risk result is shown below.", type: "success" });
    },
    onError: (mutationError: unknown) => {
      const message = getErrorMessage(mutationError, "Unable to create the risk assessment. Please try again.");
      setCreateError(message);
      toast({ title: "Risk assessment not saved", message, type: "error" });
    },
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => safetyApi.approveRiskAssessment(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["risk-assessments"] });
      qc.invalidateQueries({ queryKey: ["risk-assessments-summary"] });
      setActionError("");
      toast({ title: "Risk assessment approved", message: "The independent approval is recorded.", type: "success" });
    },
    onError: (mutationError: unknown) => {
      const message = getErrorMessage(mutationError, "Unable to approve this risk assessment.");
      setActionError(message);
      toast({ title: "Approval not recorded", message, type: "error" });
    },
  });

  const downloadPdf = async (assessmentId: string) => {
    try {
      const blob = await safetyApi.downloadRiskAssessmentPdf(assessmentId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `risk-assessment-${assessmentId}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch {
      setActionError("Unable to download risk assessment PDF.");
    }
  };

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Safety Management</div>
          <h1 className="app-title">Risk Assessments</h1>
          <p className="app-subtitle">Assess hazards and occurrences, define mitigations, and track residual risk.</p>
        </div>
        {canCreate && <Button
          type="button"
          onClick={() => {
            setShowForm(!showForm);
            setCreateError("");
            setLastCreated(null);
          }}
          variant="default"
          size="sm"
        >
          <Plus size={16} /> {showForm ? "Cancel" : "New Assessment"}
        </Button>}
      </header>

      {lastCreated && (
        <div role="alert" className={`mb-4 rounded-md border p-3 text-sm ${lastCreated.flight_cancelled ? "border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger" : "border-kfl-status-success-bg bg-kfl-status-success-bg/20 text-kfl-status-success"}`}>
          <strong>Assessment recorded: {lastCreated.assessment_id}</strong>
          <p className="mt-1">
            Server-calculated {riskModelLabel(lastCreated.risk_model)} result: risk score {lastCreated.risk_score ?? "—"}, {lastCreated.risk_level}.
          </p>
          {lastCreated.flight_cancelled && <p className="mt-1 font-semibold">Flight cancelled by this assessment; flight release is blocked.</p>}
          {!lastCreated.flight_cancelled && lastCreated.status !== "approved" && <p className="mt-1">Independent approval is required before flight release.</p>}
          {lastCreated.mission_id && <p className="mt-1">Linked assessment for mission {lastCreated.mission_id}.</p>}
        </div>
      )}

      {summaryError && <div role="alert" className="mb-4 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">
        Unable to load risk assessment metrics. <Button variant="outline" size="sm" type="button" onClick={() => void refetchSummary()}>
          Retry metrics
        </Button>
      </div>}
      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="app-surface p-4">
          <div className="app-label">Total Assessments</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{summaryLoading ? "…" : summaryError ? "—" : summary?.total ?? 0}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Awaiting Approval</div>
          <div className="mt-2 text-2xl font-bold text-kfl-status-warning">{summaryLoading ? "…" : summaryError ? "—" : (summary?.draft ?? 0) + (summary?.scrutiny_required ?? 0)}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">High / Critical</div>
          <div className="mt-2 text-2xl font-bold text-kfl-status-danger">{summaryLoading ? "…" : summaryError ? "—" : summary?.high_or_critical ?? 0}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Approved</div>
          <div className="mt-2 text-2xl font-bold text-kfl-status-success">{summaryLoading ? "…" : summaryError ? "—" : summary?.approved ?? 0}</div>
        </div>
      </section>

      {showForm && (
        <div className="app-surface p-5 mb-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <div className="app-label mb-1">New Risk Assessment</div>
              <p className="text-xs text-kfl-muted">Select the applicable risk model. The server calculates the result and keeps approval separate from assessment.</p>
            </div>
            <Button variant="outline" size="sm" onClick={() => { setShowForm(false); setDirty(false); setCreateError(""); }}>
              Cancel
            </Button>
          </div>
          {createError && <div role="alert" className="mb-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">{createError}</div>}
          <div className="space-y-3 mb-4">
            <FormField htmlFor="ra_model" label="Risk model" hint="Choose the model required for this assessment." required>
              <select id="ra_model" name="risk_model" className="app-input" value={riskModel} onChange={(e) => { setRiskModel(e.target.value); setDirty(true); }}>
                <option value="sms_5x5">SMS 5×5 matrix</option>
                <option value="om_flight_26">OM §2.6 flight risk tool</option>
              </select>
            </FormField>
            <FormField htmlFor="ra_title" label="Assessment title" hint="Summarize the risk being assessed." required>
              <Input id="ra_title" name="title" aria-describedby="ra_title-error" aria-invalid={!!raErrors.title} className={raErrors.title ? "border-rose-400" : ""} placeholder="Assessment title" value={title} onChange={(e) => { setTitle(e.target.value); setDirty(true); }} />
              {raErrors.title && <p id="ra_title-error" className="text-[11px] text-rose-700 mt-1">{raErrors.title}</p>}
            </FormField>
            <FormField htmlFor="ra_description" label="Description" hint="Describe the scenario, exposure, and potential consequences." required>
              <textarea id="ra_description" name="description" aria-describedby="ra_description-error" aria-invalid={!!raErrors.description} className={raErrors.description ? "border-rose-400" : ""} placeholder="Describe the risk scenario" value={description} onChange={(e) => { setDescription(e.target.value); setDirty(true); }} rows={3} />
              {raErrors.description && <p id="ra_description-error" className="text-[11px] text-rose-700 mt-1">{raErrors.description}</p>}
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="space-y-2">
              <FormField htmlFor="ra_hazard" label="Hazard IDs" hint="Add one or more existing hazard records.">
                <div className="flex gap-2">
                  <Input id="ra_hazard" name="hazard_id" className="flex-1" placeholder="e.g. HAZ-001" value={newHazardId} onChange={(e) => setNewHazardId(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addHazard()} />
                  <Button type="button" onClick={addHazard} variant="outline" size="sm" disabled={!newHazardId.trim() || hazardIds.includes(newHazardId.trim())}>
                    Add
                  </Button>
                </div>
                {hazardIds.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {hazardIds.map((hid) => (
                      <span key={hid} className="inline-flex items-center gap-1.5 rounded-md border border-kfl-border bg-kfl-surface-subtle px-2.5 py-1.5 text-xs text-kfl-text">
                        <span className="font-mono">{hid}</span>
                        <Button type="button" onClick={() => removeHazard(hid)} variant="ghost" size="sm" className="p-1 text-kfl-muted hover:text-kfl-status-danger hover:bg-kfl-status-danger-bg/20" aria-label={`Remove hazard ${hid}`}>
                          ×
                        </Button>
                      </span>
                    ))}
                  </div>
                )}
                <p className="text-[10px] text-kfl-muted mt-1">
                  {hazardIds.length === 0 ? "No hazards linked" : `${hazardIds.length} hazard${hazardIds.length === 1 ? "" : "s"} linked`}
                </p>
              </FormField>
            </div>
            <div className="space-y-3">
              <FormField htmlFor="ra_occurrence" label="Occurrence ID" hint="Optional link to an existing occurrence.">
                <Input id="ra_occurrence" name="occurrence_id" placeholder="e.g. OCC-..." value={occurrenceId} onChange={(e) => { setOccurrenceId(e.target.value); setDirty(true); }} />
              </FormField>
              <FormField htmlFor="ra_mission_search" label="Search planned missions" hint="Search by mission ID, title, or location.">
                <Input id="ra_mission_search" name="mission_search" value={missionSearch} onChange={(e) => setMissionSearch(e.target.value)} />
              </FormField>
              <FormField htmlFor="ra_mission" label="Mission" hint="Optional. This assessment becomes the mission's active risk assessment.">
                <select id="ra_mission" name="mission_id" className="app-input" value={missionId} onChange={(e) => { setMissionId(e.target.value); setDirty(true); }}>
                  <option value="">No mission link</option>
                  {plannedMissions.map((mission: { mission_id: string; title: string }) => (
                    <option key={mission.mission_id} value={mission.mission_id}>{mission.mission_id} — {mission.title}</option>
                  ))}
                </select>
                {missionsError && <p role="alert" className="mt-1 text-[11px] text-rose-700">Unable to load planned missions; an assessment can still be created without a mission link.</p>}
              </FormField>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <FormField htmlFor="ra_likelihood" label="Likelihood" required>
              <select id="ra_likelihood" name="likelihood" value={likelihood} onChange={(e) => { setLikelihood(e.target.value); setDirty(true); }} className="app-input">
                <option value="rare">Rare</option>
                <option value="remote">Remote</option>
                <option value="unlikely">Unlikely</option>
                <option value="occasional">Occasional</option>
                <option value="possible">Possible</option>
                <option value="probable">Probable</option>
                <option value="likely">Likely</option>
                <option value="frequent">Frequent</option>
                <option value="almost_certain">Almost certain</option>
              </select>
            </FormField>
            <FormField htmlFor="ra_severity" label="Severity" required>
              <select id="ra_severity" name="severity" value={severity} onChange={(e) => { setSeverity(e.target.value); setDirty(true); }} className="app-input">
                <option value="negligible">Negligible</option>
                <option value="minor">Minor</option>
                <option value="major">Major</option>
                <option value="moderate">Moderate</option>
                <option value="hazardous">Hazardous</option>
                <option value="critical">Critical</option>
                <option value="catastrophic">Catastrophic</option>
              </select>
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            {riskModel === "sms_5x5" ? (
              <FormField htmlFor="ra_risk" label="Risk level" hint="The backend validates the selected band against the SMS matrix." required>
                <select id="ra_risk" name="risk_level" aria-invalid={!!raErrors.risk_level} className={`app-input ${raErrors.risk_level ? "border-rose-400" : ""}`} value={riskLevel} onChange={(e) => { setRiskLevel(e.target.value); setDirty(true); }}>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
                {raErrors.risk_level && <p className="mt-1 text-[11px] text-rose-700">{raErrors.risk_level}</p>}
              </FormField>
            ) : (
              <FormField htmlFor="ra_exposure" label="Exposure" hint="Required by the OM §2.6 flight risk model." required>
                <select id="ra_exposure" name="exposure" aria-invalid={!!raErrors.exposure} className={`app-input ${raErrors.exposure ? "border-rose-400" : ""}`} value={exposure} onChange={(e) => { setExposure(e.target.value); setDirty(true); }}>
                  <option value="rare">Rare</option>
                  <option value="remote">Remote</option>
                  <option value="unlikely">Unlikely</option>
                  <option value="occasional">Occasional</option>
                  <option value="possible">Possible</option>
                  <option value="probable">Probable</option>
                  <option value="likely">Likely</option>
                  <option value="frequent">Frequent</option>
                  <option value="almost_certain">Almost certain</option>
                </select>
                {raErrors.exposure && <p className="mt-1 text-[11px] text-rose-700">{raErrors.exposure}</p>}
              </FormField>
            )}
            <div className="flex items-end text-xs text-kfl-muted">
              Risk result, scrutiny, and cancellation decisions are returned by the server and cannot be client-overridden.
            </div>
          </div>
          <div className="space-y-3 mb-4">
            <FormField htmlFor="ra_mitigation" label="Mitigation measures" hint="Controls or actions to reduce likelihood or severity.">
              <textarea id="ra_mitigation" name="mitigation_measures" placeholder="Mitigation measures" value={mitigationMeasures} onChange={(e) => { setMitigationMeasures(e.target.value); setDirty(true); }} rows={2} />
            </FormField>
            <FormField htmlFor="ra_residual" label="Residual risk" hint="Remaining risk after mitigations are applied.">
              <Input id="ra_residual" name="residual_risk" placeholder="Residual risk statement" value={residualRisk} onChange={(e) => { setResidualRisk(e.target.value); setDirty(true); }} />
            </FormField>
          </div>

          {/* PDF-aligned fields matching KFL Drone Risk Assessment template */}
          <div className="rounded-lg border border-kfl-border bg-kfl-surface-subtle p-4 mb-4">
            <div className="flex items-center gap-2 mb-3">
              <Download size={14} className="text-kfl-blue" />
              <span className="text-xs font-semibold text-kfl-text uppercase tracking-wider">KFL Risk Assessment Template Fields</span>
            </div>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <FormField htmlFor="ra_pic_name" label="PIC Full Name" hint="Pilot in Command full name as it will appear on the signed form." required>
                <Input id="ra_pic_name" name="pic_full_name" aria-invalid={!!raErrors.pic_full_name} className={raErrors.pic_full_name ? "border-rose-400" : ""} placeholder="PIC full name" value={picFullName} onChange={(e) => { setPicFullName(e.target.value); setDirty(true); }} />
              </FormField>
              <FormField htmlFor="ra_location" label="Location / Coordinates" hint="Flight location or GPS coordinates." required>
                <Input id="ra_location" name="location_coordinates" aria-invalid={!!raErrors.location_coordinates} className={raErrors.location_coordinates ? "border-rose-400" : ""} placeholder="Location / coordinates" value={locationCoordinates} onChange={(e) => { setLocationCoordinates(e.target.value); setDirty(true); }} />
              </FormField>
              <FormField htmlFor="ra_drone" label="Drone Type / Model" hint="Aircraft type and model." required>
                <Input id="ra_drone" name="drone_type_model" aria-invalid={!!raErrors.drone_type_model} className={raErrors.drone_type_model ? "border-rose-400" : ""} placeholder="Drone type / model" value={droneTypeModel} onChange={(e) => { setDroneTypeModel(e.target.value); setDirty(true); }} />
              </FormField>
              <FormField htmlFor="ra_project" label="Project Type" hint="Type of operation (e.g. survey, inspection, training)." required>
                <Input id="ra_project" name="project_type" aria-invalid={!!raErrors.project_type} className={raErrors.project_type ? "border-rose-400" : ""} placeholder="Project type" value={projectType} onChange={(e) => { setProjectType(e.target.value); setDirty(true); }} />
              </FormField>
            </div>
            <div className="space-y-3 mb-4">
              <FormField htmlFor="ra_flight_decision" label="Flight Decision" hint="Proceed or Hold based on overall residual risk." required>
                <select id="ra_flight_decision" name="flight_decision" className="app-input" value={flightDecision} onChange={(e) => { setFlightDecision(e.target.value); setDirty(true); }}>
                  <option value="">Select decision</option>
                  <option value="Proceed">Proceed</option>
                  <option value="Hold">Hold</option>
                </select>
                {raErrors.flight_decision && <p className="mt-1 text-[11px] text-rose-700">{raErrors.flight_decision}</p>}
              </FormField>
              <FormField htmlFor="ra_conditions" label="Additional Conditions / Notes" hint="Conditions or notes for the flight decision.">
                <textarea id="ra_conditions" name="conditions_notes" placeholder="Additional conditions or notes" value={conditionsNotes} onChange={(e) => { setConditionsNotes(e.target.value); setDirty(true); }} rows={2} />
              </FormField>
            </div>
          </div>

          {/* KFL Predefined Hazard Checklist */}
          <div className="rounded-lg border border-kfl-border bg-kfl-surface-subtle p-4 mb-4">
            <div className="flex items-center gap-2 mb-3">
              <ShieldCheck size={14} className="text-kfl-blue" />
              <span className="text-xs font-semibold text-kfl-text uppercase tracking-wider">Predefined Hazards (KFL Template)</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
              {KFL_HAZARDS.map((hazard) => (
                <div key={hazard.id} className="p-2 rounded border border-kfl-border bg-kfl-surface text-xs">
                  <label className="flex items-start gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedHazards[hazard.id] ?? false}
                      onChange={() => setSelectedHazards({ ...selectedHazards, [hazard.id]: !selectedHazards[hazard.id] })}
                      className="mt-0.5 shrink-0 text-kfl-blue"
                    />
                    <div className="flex-1">
                      <div className="font-semibold text-kfl-text">{hazard.name}</div>
                      <div className="text-[10px] text-kfl-muted">{hazard.risk}</div>
                      <div className="text-[10px] text-kfl-muted">{hazard.mitigation}</div>
                      <div className="text-[10px] font-mono text-kfl-muted">{hazard.score} ({hazard.ls})</div>
                    </div>
                  </label>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-kfl-muted">Select hazards present and verify the listed controls before flight. Scores assume controls are in place.</p>
          </div>

          {/* Sign-off block */}
          <div className="rounded-lg border border-kfl-border bg-kfl-surface-subtle p-4 mb-4">
            <div className="flex items-center gap-2 mb-3">
              <UserCheck size={14} className="text-kfl-blue" />
              <span className="text-xs font-semibold text-kfl-text uppercase tracking-wider">Sign-off</span>
            </div>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <FormField htmlFor="ra_head_safety" label="Approved by Head of Safety" hint="Name of the Head of Safety approving this assessment.">
                <Input id="ra_head_safety" name="head_of_safety" value={headOfSafetyName} onChange={(e) => { setHeadOfSafetyName(e.target.value); setDirty(true); }} placeholder="Head of Safety name" />
              </FormField>
              <FormField htmlFor="ra_approval_date" label="Approval Date" hint="Date of Head of Safety approval.">
                <Input id="ra_approval_date" name="approval_date" type="date" value={approvalDate} onChange={(e) => { setApprovalDate(e.target.value); setDirty(true); }} />
              </FormField>
              <FormField htmlFor="ra_safety_signature" label="Head of Safety Signature" hint="Signature of the Head of Safety.">
                <Input id="ra_safety_signature" name="safety_signature" value={safetySignature} onChange={(e) => { setSafetySignature(e.target.value); setDirty(true); }} placeholder="Signature" />
              </FormField>
              <FormField htmlFor="ra_date_filed" label="Date Filed" hint="Date the assessment was filed.">
                <Input id="ra_date_filed" name="date_filed" type="date" value={assessmentDate} onChange={(e) => { setAssessmentDate(e.target.value); setDirty(true); }} />
              </FormField>
            </div>
          </div>
          <Button
            type="button"
            disabled={!raIsValid || createMutation.isPending}
            onClick={() => {
              setCreateError("");
              createMutation.mutate({
                title: title.trim(),
                description: description.trim(),
                pic_full_name: picFullName.trim(),
                location_coordinates: locationCoordinates.trim(),
                drone_type_model: droneTypeModel.trim(),
                project_type: projectType.trim(),
                flight_decision: flightDecision,
                conditions_notes: conditionsNotes.trim() || null,
                head_of_safety_name: headOfSafetyName.trim() || null,
                safety_signature: safetySignature.trim() || null,
                approval_date: approvalDate || null,
                date_filed: assessmentDate || null,
                hazard_ids: hazardIds,
                occurrence_id: occurrenceId.trim() || null,
                mission_id: missionId || null,
                likelihood,
                severity,
                risk_model: riskModel,
                ...(riskModel === "sms_5x5" ? { risk_level: riskLevel } : { exposure }),
                mitigation_measures: mitigationMeasures.trim() || null,
                residual_risk: residualRisk.trim() || null,
              });
            }}
            variant="default"
            size="sm"
            className="w-full disabled:opacity-60"
          >
            {createMutation.isPending ? "Submitting…" : "Submit Assessment"}
          </Button>
        </div>
      )}

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-semibold text-kfl-text">Risk Assessments</div>
            <p className="mt-1 text-xs text-kfl-muted">Filters are applied on the server before pagination.</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <select id="ra_status_filter" name="status" aria-label="Filter by status" className="app-input w-full md:w-auto" value={statusFilter} onChange={(e) => { setPage(0); setStatusFilter(e.target.value); }}>
              <option value="">All statuses</option>
              <option value="draft">Draft</option>
              <option value="scrutiny_required">Scrutiny required</option>
              <option value="approved">Approved</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <select id="ra_risk_filter" name="risk_level" aria-label="Filter by risk level" className="app-input w-full md:w-auto" value={riskFilter} onChange={(e) => { setPage(0); setRiskFilter(e.target.value); }}>
              <option value="">All risk levels</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>
        </div>

        {actionError && <div role="alert" className="m-4 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">{actionError}</div>}
        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading risk assessments…</div>
        ) : isError ? (
          <div className="p-10 text-center" role="alert">
            <p className="text-sm font-semibold text-kfl-status-danger">Unable to load risk assessments: {getErrorMessage(error, "Please try again.")}</p>
            <Button variant="outline" size="sm" type="button" onClick={() => void refetch()}>
              Retry risk assessments
            </Button>
          </div>
        ) : assessments.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <ShieldCheck size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">{statusFilter || riskFilter ? "No assessments match these filters." : "No risk assessments recorded."}</p>
            {!statusFilter && !riskFilter && <p className="mt-1 text-xs text-kfl-muted">Create an assessment to begin risk tracking.</p>}
            {(statusFilter || riskFilter) && <Button variant="outline" size="sm" type="button" onClick={() => { setStatusFilter(""); setRiskFilter(""); setPage(0); }}>
              Clear filters
            </Button>}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                  <tr>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Assessment ID</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Title</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Linked To</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Model / Score</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Risk</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                    <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-kfl-border">
                  {assessments.map((r) => {
                    const links = [
                      ...(r.hazard_ids ?? []).map((hazardId: string) => `Hazard ${hazardId}`),
                      ...(r.occurrence_id ? [`Occurrence ${r.occurrence_id}`] : []),
                      ...(r.mission_id ? [`Mission ${r.mission_id}`] : []),
                    ];
                    const approvalPending = ["draft", "scrutiny_required"].includes(r.status) && !r.flight_cancelled;
                    const canApproveThis = canApprove && approvalPending && r.can_approve_for_current_user === true;
                    return (
                      <tr key={r.assessment_id} className="transition hover:bg-kfl-surface-subtle group">
                        <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{r.assessment_id}</td>
                        <td className="px-4 py-4">
                          <div className="font-semibold text-kfl-text">{r.title}</div>
                          <div className="mt-1 text-xs text-kfl-muted line-clamp-1">{r.description}</div>
                          <div className="mt-1 text-[11px] text-kfl-muted">Assessor: {r.assessor_id}</div>
                        </td>
                        <td className="px-4 py-4 text-sm text-kfl-secondary">{links.length ? links.join(", ") : "—"}</td>
                        <td className="px-4 py-4 text-sm text-kfl-secondary">
                          <div>{riskModelLabel(r.risk_model)}</div>
                          <div className="mt-1 text-xs text-kfl-muted">Score {r.risk_score ?? "—"}{r.exposure ? ` · Exposure ${r.exposure}` : ""}</div>
                        </td>
                        <td className="px-4 py-4"><Badge variant={r.risk_level === "critical" || r.risk_level === "high" ? "destructive" : r.risk_level === "medium" ? "secondary" : "default"} className={`badge ${r.risk_level === "critical" || r.risk_level === "high" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : r.risk_level === "medium" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : "bg-kfl-status-info-bg text-kfl-status-info"}`}>{r.risk_level}</Badge></td>
                        <td className="px-4 py-4"><Badge variant={r.status === "approved" ? "default" : r.status === "scrutiny_required" ? "secondary" : r.status === "cancelled" ? "destructive" : "outline"} className={`badge ${r.status === "approved" ? "bg-kfl-status-info-bg text-kfl-status-info" : r.status === "scrutiny_required" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : r.status === "cancelled" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : "bg-kfl-status-info-bg text-kfl-status-info"}`}>{r.status.replace(/_/g, " ")}</Badge></td>
                        <td className="px-4 py-4 text-right text-sm">
                          {canApproveThis ? (
                            <Button type="button" aria-label={`Approve ${r.assessment_id}`} disabled={approveMutation.isPending} variant="outline" size="sm" onClick={() => approveMutation.mutate(r.assessment_id)} className="inline-flex items-center gap-1">
                              <CheckCircle size={13} /> Approve
                            </Button>
                          ) : canApprove && approvalPending && r.can_approve_for_current_user !== true ? (
                            <span className="text-xs text-kfl-muted">Independent reviewer required</span>
                          ) : <span className="text-xs text-kfl-muted">—</span>}
                          <Button
                            type="button"
                            aria-label={`Download PDF ${r.assessment_id}`}
                            size="sm"
                            onClick={() => downloadPdf(r.assessment_id)}
                            className="mt-2 inline-flex items-center gap-1 text-xs text-kfl-blue hover:underline border-0 bg-transparent p-0"
                          >
                            <Download size={12} /> PDF
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-kfl-border p-4">
              <span className="text-sm text-kfl-muted">Page {page + 1}</span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" type="button" disabled={page === 0 || isLoading} onClick={() => setPage((current) => current - 1)}>
                  Previous page
                </Button>
                <Button variant="outline" size="sm" type="button" disabled={!hasNextPage || isLoading} onClick={() => setPage((current) => current + 1)}>
                  Next page
                </Button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
