"use client";
import { create } from "zustand";

interface AuthState {
  username: string | null;
  setAuth: (username: string | null) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  username: typeof window !== "undefined" ? localStorage.getItem("username") : null,
  setAuth: (username) => {
    if (username) localStorage.setItem("username", username);
    else localStorage.removeItem("username");
    set({ username });
  },
  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("username");
    set({ username: null });
    window.location.href = "/login";
  },
}));

interface UiState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}

export const useUi = create<UiState>((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));

const CURRENT_ACCOUNT_KEY = "current_account_id";

interface PhoneState {
  currentAccountId: number | null;
  setCurrentAccountId: (id: number | null) => void;
}

function storedAccountId(): number | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(CURRENT_ACCOUNT_KEY);
  if (raw === null) return null;
  const n = Number(raw);
  if (!Number.isInteger(n) || n <= 0) {
    localStorage.removeItem(CURRENT_ACCOUNT_KEY);
    return null;
  }
  return n;
}

export const usePhone = create<PhoneState>((set) => ({
  currentAccountId: storedAccountId(),
  setCurrentAccountId: (id) => {
    if (id === null) localStorage.removeItem(CURRENT_ACCOUNT_KEY);
    else localStorage.setItem(CURRENT_ACCOUNT_KEY, String(id));
    set({ currentAccountId: id });
  },
}));
