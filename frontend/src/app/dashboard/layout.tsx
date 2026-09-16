"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Header, MobileNav, Sidebar, TopBar } from "@/components/layout";
import { Toaster } from "@/components/toast";
import { useAuth } from "@/stores/stores";
import { useRealtimeFeed } from "@/hooks/use-realtime";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { username, ready, setAuth } = useAuth();
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.replace("/login");
    } else if (!username) {
      setAuth(localStorage.getItem("username") ?? "admin");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useRealtimeFeed(!!token);

  if (!token) return null;

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <TopBar />
        <main className="flex-1 space-y-6 p-4 pb-20 md:p-6 md:pb-6">{children}</main>
      </div>
        <Toaster />
        <MobileNav />
    </div>
  );
}
