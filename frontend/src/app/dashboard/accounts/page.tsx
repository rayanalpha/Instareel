"use client";
import { useState } from "react";
import Link from "next/link";
import { Card, EmptyState, Field, Spinner, StatusBadge } from "@/components/ui";
import { useAccounts, useApiMutation } from "@/hooks/use-api";
import { timeAgo } from "@/lib/utils";
import type { Account } from "@/types/models";

export default function AccountsPage() {
  const { data, isLoading } = useAccounts();
  const create = useApiMutation("post", [["accounts"]]);
  const remove = useApiMutation("delete", [["accounts"]]);
  const action = useApiMutation("post", [["accounts"]]);
  const [form, setForm] = useState({ username: "", password: "", max_daily_posts: 3 });
  const accounts = (data ?? []) as Account[];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Instagram accounts</h1>
      <Card>
        <div className="grid gap-3 md:grid-cols-4">
          <Field label="Username"><input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="instagram_user" /></Field>
          <Field label="Password"><input className="input" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
          <Field label="Max posts/day"><input className="input" type="number" min={1} max={20} value={form.max_daily_posts} onChange={(e) => setForm({ ...form, max_daily_posts: Number(e.target.value) })} /></Field>
          <div className="flex items-end">
            <button
              className="btn-primary w-full" disabled={!form.username || !form.password || create.isPending}
              onClick={() => { create.mutate({ url: "/accounts", body: form }); setForm({ username: "", password: "", max_daily_posts: 3 }); }}
            >
              Add account
            </button>
          </div>
        </div>
      </Card>
      {isLoading ? <Spinner /> : accounts.length === 0 ? (
        <EmptyState title="No accounts" hint="Add your first Instagram account above." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {accounts.map((a) => (
            <Card key={a.id}>
              <div className="flex items-center gap-2">
                <Link href={`/dashboard/accounts/${a.id}`} className="font-semibold hover:text-emerald-500">@{a.username}</Link>
                <span className="ml-auto"><StatusBadge status={a.status} /></span>
              </div>
              <p className="mt-1 text-xs text-zinc-500">
                {a.posts_today}/{a.max_daily_posts} today · {a.total_posts} total · {a.total_views} views · last post {timeAgo(a.last_post)}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="btn-ghost !px-3 !py-1.5 text-xs" onClick={() => action.mutate({ url: `/accounts/${a.id}/login` })}>Login</button>
                <button className="btn-ghost !px-3 !py-1.5 text-xs" onClick={() => action.mutate({ url: `/accounts/${a.id}/test-session` })}>Test session</button>
                {a.status === "active"
                  ? <button className="btn-ghost !px-3 !py-1.5 text-xs" onClick={() => action.mutate({ url: `/accounts/${a.id}/cooldown` })}>Cooldown</button>
                  : <button className="btn-ghost !px-3 !py-1.5 text-xs" onClick={() => action.mutate({ url: `/accounts/${a.id}/activate` })}>Activate</button>}
                <button
                  className="btn-ghost !px-3 !py-1.5 text-xs text-red-500"
                  onClick={() => { if (confirm(`Remove @${a.username}?`)) remove.mutate({ url: `/accounts/${a.id}` }); }}
                >
                  Remove
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
