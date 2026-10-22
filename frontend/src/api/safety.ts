import api from "./client";
import { Occurrence, Hazard, SafetyAction } from "../types";

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

  listSafetyActions: (params?: Record<string, any>) =>
    api.get<SafetyAction[]>("/p1/safety-actions", { params }).then((r: any) => r.data),
  createSafetyAction: (data: any) =>
    api.post<SafetyAction>("/p1/safety-actions", data).then((r: any) => r.data),
  updateSafetyAction: (id: string, data: any) =>
    api.patch<SafetyAction>(`/p1/safety-actions/${id}`, data).then((r: any) => r.data),

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
};
