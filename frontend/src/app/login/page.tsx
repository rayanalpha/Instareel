"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";
import { Clapperboard } from "lucide-react";
import { apiBase } from "@/lib/api";
import { useAuth } from "@/stores/stores";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  const { setAuth } = useAuth();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { data } = await axios.post(`${apiBase()}/api/v1/auth/login`, { username, password });
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      setAuth(username);
      router.push("/dashboard");
    } catch {
      setError("Invalid credentials. Check ADMIN_USERNAME / ADMIN_PASSWORD in the backend .env.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4 p-8">
        <div className="flex items-center gap-2">
          <Clapperboard className="h-7 w-7 text-emerald-500" />
          <h1 className="text-xl font-extrabold tracking-tight">IG Funnel</h1>
        </div>
        <p className="text-sm text-zinc-500">Sign in to the admin dashboard.</p>
        <div>
          <span className="label">Username</span>
          <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </div>
        <div>
          <span className="label">Password</span>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </div>
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </main>
  );
}
