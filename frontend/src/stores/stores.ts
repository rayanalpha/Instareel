"use client";
import { create } from "zustand";

interface AuthState {
  username: string | null;
  ready: boolean;
  setAuth: (username: string | null) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  username: typeof window !== "undefined" ? localStorage.getItem("username") : null,
  ready: false,
  setAuth: (username) => {
    if (username) localStorage.setItem("username", username);
    else localStorage.removeItem("username");
    set({ username, ready: true });
  },
  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("username");
    set({ username: null, ready: true });
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
