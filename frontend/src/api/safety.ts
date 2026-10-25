import api from "./client";
import { Occurrence, Hazard, SafetyAction, RiskAssessment, Investigation, AuditEvent, TrainingRecord } from "../types";

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
};
