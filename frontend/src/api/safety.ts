import api from "./client";
import { Occurrence, Hazard, SafetyAction, RiskAssessment, Investigation, AuditEvent, TrainingRecord, MaintenanceRecord, CrewMember, DutyRecord, CrewQualification, ChangeRequest, ReviewComment } from "../types";

export const safetyApi = {
  listOccurrences: (params?: Record<string, any>) =>
    api.get<Occurrence[]>("/p1/occurrences", { params }).then((r: any) => r.data),
  getOccurrence: (id: string) =>
    api.get<Occurrence>(`/p1/occurrences/${id}`).then((r: any) => r.data),
  createOccurrence: (data: any) =>
    api.post<Occurrence>("/p1/occurrences", data).then((r: any) => r.data),
  updateOccurrence: (id: string, data: any) =>
    api.patch<Occurrence>(`/p1/occurrences/${id}`, data).then((r: any) => r.data),
  acknowledgeOccurrence: (id: string) =>
    api.post(`/p1/occurrences/${id}/acknowledge`).then((r: any) => r.data),

  listHazards: (params?: Record<string, any>) =>
    api.get<Hazard[]>("/p1/hazards", { params }).then((r: any) => r.data),
  createHazard: (data: any) =>
    api.post<Hazard>("/p1/hazards", data).then((r: any) => r.data),
  updateHazard: (id: string, data: any) =>
    api.patch<Hazard>(`/p1/hazards/${id}`, data).then((r: any) => r.data),

  listRiskAssessments: (params?: Record<string, any>) =>
    api.get<RiskAssessment[]>("/p1/risk-assessments", { params }).then((r: any) => r.data),
  createRiskAssessment: (data: any) =>
    api.post<RiskAssessment>("/p1/risk-assessments", data).then((r: any) => r.data),
  updateRiskAssessment: (id: string, data: any) =>
    api.patch<RiskAssessment>(`/p1/risk-assessments/${id}`, data).then((r: any) => r.data),

  listInvestigations: (params?: Record<string, any>) =>
    api.get<Investigation[]>("/p1/investigations", { params }).then((r: any) => r.data),
  createInvestigation: (data: any) =>
    api.post<Investigation>("/p1/investigations", data).then((r: any) => r.data),
  updateInvestigation: (id: string, data: any) =>
    api.patch<Investigation>(`/p1/investigations/${id}`, data).then((r: any) => r.data),

  listSafetyActions: (params?: Record<string, any>) =>
    api.get<SafetyAction[]>("/p1/safety-actions", { params }).then((r: any) => r.data),
  createSafetyAction: (data: any) =>
    api.post<SafetyAction>("/p1/safety-actions", data).then((r: any) => r.data),
  updateSafetyAction: (id: string, data: any) =>
    api.patch<SafetyAction>(`/p1/safety-actions/${id}`, data).then((r: any) => r.data),

  listAuditEvents: (params?: Record<string, any>) =>
    api.get<AuditEvent[]>("/p0/audit-events", { params }).then((r: any) => r.data),

  getTrends: () =>
    api.get("/p1/safety/trends").then((r: any) => r.data),
  getDeadlines: (daysAhead?: number) =>
    api.get("/p1/deadlines", { params: { days_ahead: daysAhead ?? 30 } }).then((r: any) => r.data),
  getNotificationStatus: () =>
    api.get("/p1/notifications/status").then((r: any) => r.data),
  listNotifications: (params?: Record<string, any>) =>
    api.get("/p1/notifications", { params }).then((r: any) => r.data),
  getUnreadCount: () =>
    api.get("/p1/notifications/unread-count").then((r: any) => r.data),
  triggerNotificationCheck: () =>
    api.post("/p1/notifications/check").then((r: any) => r.data),
  getNotificationPreferences: () =>
    api.get("/p1/notification-preferences").then((r: any) => r.data),
  updateNotificationPreferences: (data: any) =>
    api.put("/p1/notification-preferences", null, { params: data }).then((r: any) => r.data),
  markNotificationRead: (id: string) =>
    api.patch(`/p1/notifications/${id}/read`).then((r: any) => r.data),

  listTrainingRecords: (params?: Record<string, any>) =>
    api.get<TrainingRecord[]>("/p1/training-records", { params }).then((r: any) => r.data),
  createTrainingRecord: (data: any) =>
    api.post<TrainingRecord>("/p1/training-records", data).then((r: any) => r.data),
  updateTrainingRecord: (id: string, data: any) =>
    api.patch<TrainingRecord>(`/p1/training-records/${id}`, data).then((r: any) => r.data),
  deleteTrainingRecord: (id: string) =>
    api.delete(`/p1/training-records/${id}`).then((r: any) => r.data),

  listMaintenanceRecords: (params?: Record<string, any>) =>
    api.get<MaintenanceRecord[]>("/p1/maintenance-records", { params }).then((r: any) => r.data),
  createMaintenanceRecord: (data: any) =>
    api.post<MaintenanceRecord>("/p1/maintenance-records", data).then((r: any) => r.data),
  updateMaintenanceRecord: (id: string, data: any) =>
    api.patch<MaintenanceRecord>(`/p1/maintenance-records/${id}`, data).then((r: any) => r.data),
  deleteMaintenanceRecord: (id: string) =>
    api.delete(`/p1/maintenance-records/${id}`).then((r: any) => r.data),

  listCrewMembers: (params?: Record<string, any>) =>
    api.get<CrewMember[]>("/p1/crew-members", { params }).then((r: any) => r.data),
  createCrewMember: (data: any) =>
    api.post<CrewMember>("/p1/crew-members", data).then((r: any) => r.data),
  updateCrewMember: (id: string, data: any) =>
    api.patch<CrewMember>(`/p1/crew-members/${id}`, data).then((r: any) => r.data),
  deleteCrewMember: (id: string) =>
    api.delete(`/p1/crew-members/${id}`).then((r: any) => r.data),

  listDutyRecords: (params?: Record<string, any>) =>
    api.get<DutyRecord[]>("/p1/duty-records", { params }).then((r: any) => r.data),
  createDutyRecord: (data: any) =>
    api.post<DutyRecord>("/p1/duty-records", data).then((r: any) => r.data),
  updateDutyRecord: (id: string, data: any) =>
    api.patch<DutyRecord>(`/p1/duty-records/${id}`, data).then((r: any) => r.data),
  deleteDutyRecord: (id: string) =>
    api.delete(`/p1/duty-records/${id}`).then((r: any) => r.data),

  listCrewQualifications: (params?: Record<string, any>) =>
    api.get<CrewQualification[]>("/p1/crew-qualifications", { params }).then((r: any) => r.data),
  createCrewQualification: (data: any) =>
    api.post<CrewQualification>("/p1/crew-qualifications", data).then((r: any) => r.data),
  updateCrewQualification: (id: string, data: any) =>
    api.patch<CrewQualification>(`/p1/crew-qualifications/${id}`, data).then((r: any) => r.data),
  deleteCrewQualification: (id: string) =>
    api.delete(`/p1/crew-qualifications/${id}`).then((r: any) => r.data),

  listChangeRequests: (params?: Record<string, any>) =>
    api.get<ChangeRequest[]>("/p1/change-requests", { params }).then((r: any) => r.data),
  getChangeRequest: (id: string) =>
    api.get<ChangeRequest>(`/p1/change-requests/${id}`).then((r: any) => r.data),
  createChangeRequest: (data: any) =>
    api.post<ChangeRequest>("/p1/change-requests", data).then((r: any) => r.data),
  updateChangeRequest: (id: string, data: any) =>
    api.patch<ChangeRequest>(`/p1/change-requests/${id}`, data).then((r: any) => r.data),
  deleteChangeRequest: (id: string) =>
    api.delete(`/p1/change-requests/${id}`).then((r: any) => r.data),
  submitChangeRequest: (id: string) =>
    api.post(`/p1/change-requests/${id}/submit`).then((r: any) => r.data),
  reviewChangeRequest: (id: string, data: any) =>
    api.post(`/p1/change-requests/${id}/review`, data).then((r: any) => r.data),
  approveChangeRequest: (id: string, data: any) =>
    api.post(`/p1/change-requests/${id}/approve`, data).then((r: any) => r.data),
  rejectChangeRequest: (id: string, data: any) =>
    api.post(`/p1/change-requests/${id}/reject`, data).then((r: any) => r.data),
  listReviewComments: (crId: string) =>
    api.get<ReviewComment[]>(`/p1/change-requests/${crId}/comments`).then((r: any) => r.data),
  addReviewComment: (crId: string, data: any) =>
    api.post<ReviewComment>(`/p1/change-requests/${crId}/comments`, data).then((r: any) => r.data),
};
