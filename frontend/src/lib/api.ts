import axios from "axios";

const baseURL =
  (typeof window !== "undefined" && (window as unknown as { __API_URL?: string }).__API_URL) ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export const api = axios.create({ baseURL: `${baseURL}/api/v1`, timeout: 30000 });

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshing = false;

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retried && typeof window !== "undefined") {
      original._retried = true;
      const refresh = localStorage.getItem("refresh_token");
      if (refresh && !refreshing) {
        refreshing = true;
        try {
          const { data } = await axios.post(`${baseURL}/api/v1/auth/refresh`, { refresh_token: refresh });
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem("refresh_token", data.refresh_token);
          original.headers.Authorization = `Bearer ${data.access_token}`;
          return api(original);
        } catch {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/login";
        } finally {
          refreshing = false;
        }
      }
    }
    return Promise.reject(error);
  }
);

export function apiBase(): string {
  return baseURL;
}

export function authHeaders() {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}
