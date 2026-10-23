import axios from "axios";
import { getIdentity } from "../auth/identity";

const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const identity = getIdentity();
  config.headers["X-Role"] = identity.role;
  config.headers["X-Actor"] = identity.actor;
  return config;
});

export default api;
