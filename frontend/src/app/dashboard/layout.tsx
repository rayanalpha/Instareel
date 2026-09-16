"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header, MobileNav, Sidebar, TopBar } from "@/components/layout";
import { Toaster } from "@/components/toast";
import { useAuth } from "@/stores/stores";
import { useRealtimeFeed } from "@/hooks/use-realtime";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { setAuth } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (!localStorage.getItem("access_token")) {
      router.replace("/login");
    } else if (!useAuth.getState().username) {
      setAuth(localStorage.getItem("username") ?? "admin");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Only read localStorage after mount so the server-rendered HTML (empty)
  // matches the first client render — avoids React hydration errors #418/#423.
  const token = mounted ? localStorage.getItem("access_token") : null;
  useRealtimeFeed(!!token);

  if (!mounted || !token) return null;

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
