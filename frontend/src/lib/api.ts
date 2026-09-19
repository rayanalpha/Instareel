import axios from "axios";

/**
 * Browser-side API host. The dashboard itself is served by Next.js, so the
 * default same-origin rewrite (/api -> FastAPI via next.config.js rewrites)
 * when NEXT_PUBLIC_API_URL is unset keeps everything on one origin and the
 * browser never triggers CORS/ORB.
 */
const baseURL =
  (typeof window !== "undefined" && (window as unknown as { __API_URL?: string }).__API_URL) ||
  process.env.NEXT_PUBLIC_API_URL ||
  "";

export const api = axios.create({ baseURL: `${baseURL}/api/v1`, timeout: 30000 });

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Single-flight refresh: concurrent 401s queue behind one refresh call
// instead of racing (old boolean flag dropped all but the first request).
let refreshPromise: Promise<string> | null = null;

function doRefresh(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const refresh = localStorage.getItem("refresh_token");
      if (!refresh) throw new Error("no refresh token");
      const { data } = await axios.post(`${baseURL}/api/v1/auth/refresh`, { refresh_token: refresh });
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      return data.access_token as string;
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retried && typeof window !== "undefined") {
      original._retried = true;
      try {
        const token = await doRefresh();
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      } catch {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export function apiBase(): string {
  return baseURL;
}
