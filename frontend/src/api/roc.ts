import api from "./client";
import { ROCRegister, Aircraft } from "../types";

export const rocApi = {
  listROC: (params?: Record<string, any>) =>
    api.get<ROCRegister[]>("/p1/roc", { params }).then((r: any) => r.data),
  createROC: (data: any) =>
    api.post<ROCRegister>("/p1/roc", data).then((r: any) => r.data),
  getROC: (id: string) =>
    api.get<ROCRegister>(`/p1/roc/${id}`).then((r: any) => r.data),
  updateROC: (id: string, data: any) =>
    api.patch<ROCRegister>(`/p1/roc/${id}`, data).then((r: any) => r.data),

  listAircraft: (params?: Record<string, any>) =>
    api.get<Aircraft[]>("/p1/aircraft", { params }).then((r: any) => r.data),
  createAircraft: (data: any) =>
    api.post<Aircraft>("/p1/aircraft", data).then((r: any) => r.data),
  getAircraft: (id: string) =>
    api.get<Aircraft>(`/p1/aircraft/${id}`).then((r: any) => r.data),
  updateAircraft: (id: string, data: any) =>
    api.patch<Aircraft>(`/p1/aircraft/${id}`, data).then((r: any) => r.data),
};
