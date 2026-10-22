import api from "./client";
import { OutsourcedFunction, SafetyKPI, SecurityReview, DGResponsibilityMatrix } from "../types";

export const p2Api = {
  // Outsourced Functions (QMS-06)
  listOutsourcedFunctions: (params?: Record<string, any>) =>
    api.get<OutsourcedFunction[]>("/p1/outsourced-functions", { params }).then((r: any) => r.data),
  createOutsourcedFunction: (data: any) =>
    api.post<OutsourcedFunction>("/p1/outsourced-functions", data).then((r: any) => r.data),
  updateOutsourcedFunction: (id: string, data: any) =>
    api.patch<OutsourcedFunction>(`/p1/outsourced-functions/${id}`, data).then((r: any) => r.data),

  // Safety KPIs (SAF-08)
  listSafetyKPIs: (params?: Record<string, any>) =>
    api.get<SafetyKPI[]>("/p1/safety-kpis", { params }).then((r: any) => r.data),
  createSafetyKPI: (data: any) =>
    api.post<SafetyKPI>("/p1/safety-kpis", data).then((r: any) => r.data),
  updateSafetyKPI: (id: string, data: any) =>
    api.patch<SafetyKPI>(`/p1/safety-kpis/${id}`, data).then((r: any) => r.data),

  // Security Reviews (SEC-06)
  listSecurityReviews: (params?: Record<string, any>) =>
    api.get<SecurityReview[]>("/p1/security-reviews", { params }).then((r: any) => r.data),
  createSecurityReview: (data: any) =>
    api.post<SecurityReview>("/p1/security-reviews", data).then((r: any) => r.data),
  updateSecurityReview: (id: string, data: any) =>
    api.patch<SecurityReview>(`/p1/security-reviews/${id}`, data).then((r: any) => r.data),

  // DG Responsibility Matrix (DG-12)
  listDGMatrix: (params?: Record<string, any>) =>
    api.get<DGResponsibilityMatrix[]>("/p1/dg-responsibility-matrix", { params }).then((r: any) => r.data),
  createDGMatrix: (data: any) =>
    api.post<DGResponsibilityMatrix>("/p1/dg-responsibility-matrix", data).then((r: any) => r.data),
  updateDGMatrix: (id: string, data: any) =>
    api.patch<DGResponsibilityMatrix>(`/p1/dg-responsibility-matrix/${id}`, data).then((r: any) => r.data),
};
