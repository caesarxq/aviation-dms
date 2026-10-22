import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  headers: {
    "X-Role": "system_admin",
    "X-Actor": "admin",
  },
});

export default api;
