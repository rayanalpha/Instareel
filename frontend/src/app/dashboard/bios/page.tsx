"use client";
import { useState } from "react";
import { Card, CardTitle, Field, Spinner } from "@/components/ui";
import { useAccounts } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { toast } from "@/components/toast";
import { timeAgo } from "@/lib/utils";
import type { Account, Bio, IgProfile } from "@/types/models";

type Privacy = "" | "private" | "public";
const privToBody = (p: Privacy) => (p === "" ? null : p === "private");

/** Error text that never comes back bare: backend detail when present,
// otherwise the HTTP status / abort reason plus a pointer to the Logs page
// (the server always logs IG failures there with the egress host). */
function errDetail(e: unknown, fallback: string) {
  const r = e as { response?: { status?: number; data?: { detail?: unknown } }; code?: string };
  const d = r?.response?.data?.detail;
  if (d) return String(d);
  if (r?.response?.status) return `${fallback} (HTTP ${r.response.status} — full trace is on the Logs page)`;
  if (r?.code === "ECONNABORTED") return `${fallback} (request timed out in the browser)`;
  return `${fallback} (no response — check the Logs page)`;
}

export default function BiosPage() {
  const { data: accounts } = useAccounts();
  const [accountId, setAccountId] = useState("");
  const [bio, setBio] = useState<Bio | null>(null);
  const [loading, setLoading] = useState(false);
  const [applyBusy, setApplyBusy] = useState<string | null>(null);
  const [picBusy, setPicBusy] = useState(false);
  const [opError, setOpError] = useState("");
  const [current, setCurrent] = useState<IgProfile | null | undefined>(undefined);
  const [loadingCurrent, setLoadingCurrent] = useState(false);

  // Per-section drafts, seeded from the loaded config.
  const [dText, setDText] = useState("");
  const [dLink, setDLink] = useState("");
  const [dName, setDName] = useState("");
  const [dPriv, setDPriv] = useState<Privacy>("");

  async function selectAccount(id: string) {
    setAccountId(id);
    setBio(null);
    setCurrent(undefined);
    if (!id) return;
    setLoading(true);
    try {
      const { data } = await api.post("/bios/ensure", { account_id: Number(id) });
      const b = data as Bio;
      setBio(b);
      setDText(b.text ?? "");
      setDLink(b.link_url ?? "");
      setDName(b.full_name ?? "");
      setDPriv(b.make_private === null || b.make_private === undefined ? "" : b.make_private ? "private" : "public");
    } catch {
      setOpError("Could not load profile config");
    } finally {
      setLoading(false);
    }
  }

  /** Save one section, then apply only that section to Instagram. */
  async function saveAndApply(section: string, patch: Record<string, unknown>) {
    if (!bio) return;
    setOpError("");
    setApplyBusy(section);
    try {
      const saved = (await api.put(`/bios/${bio.id}`, { account_id: bio.account_id, ...patch })).data as Bio;
      // IG round-trips through a proxy can take minutes (session + edit);
      // the global 30s axios timeout would abort with a detail-less error.
      await api.post(`/bios/${bio.id}/apply`, { fields: [section] }, { timeout: 300000 });
      toast("success", "Applied — check Instagram");
      // Re-read for the fresh last_applied timestamp.
      const list = (await api.get("/bios")).data as Bio[];
      const fresh = list.find((x) => x.id === bio.id);
      if (fresh) {
        setBio(fresh);
        if (section === "bio") setDText(fresh.text ?? "");
        if (section === "link") setDLink(fresh.link_url ?? "");
        if (section === "full_name") setDName(fresh.full_name ?? "");
        if (section === "privacy") setDPriv(fresh.make_private === null || fresh.make_private === undefined ? "" : fresh.make_private ? "private" : "public");
      } else {
        setBio(saved);
      }
    } catch (e: unknown) {
      setOpError(errDetail(e, "Apply failed"));
    } finally {
      setApplyBusy(null);
    }
  }

  async function uploadPicture(file: File | null) {
    if (!bio || !file) return;
    setOpError("");
    setPicBusy(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await api.post(`/bios/${bio.id}/picture`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });
      setBio(data as Bio);
      toast("success", "Profile picture uploaded — hit Apply picture to publish it");
    } catch (e: unknown) {
      setOpError(errDetail(e, "Picture upload failed"));
    } finally {
      setPicBusy(false);
    }
  }

  async function deletePicture() {
    if (!bio || !confirm("Remove the stored profile picture?")) return;
    setOpError("");
    setPicBusy(true);
    try {
      const { data } = await api.delete(`/bios/${bio.id}/picture`);
      setBio(data as Bio);
      toast("success", "Profile picture removed");
    } catch (e: unknown) {
      setOpError(errDetail(e, "Picture delete failed"));
    } finally {
      setPicBusy(false);
    }
  }

  async function removeLivePicture() {
    if (!bio || !confirm("Delete the CURRENT Instagram profile photo? This is immediate and cannot be undone.")) return;
    setOpError("");
    setApplyBusy("remove-live");
    try {
      await api.post(`/bios/${bio.id}/picture/remove-live`, {}, { timeout: 300000 });
      toast("success", "Live profile photo removed");
      const list = (await api.get("/bios")).data as Bio[];
      const fresh = list.find((x) => x.id === bio.id);
      if (fresh) setBio(fresh);
      setCurrent(undefined); // live snapshot is stale now — re-compare to verify
    } catch (e: unknown) {
      setOpError(errDetail(e, "Live photo removal failed"));
    } finally {
      setApplyBusy(null);
    }
  }

  async function loadCurrent() {
    if (!bio) return;
    setLoadingCurrent(true);
    try {
      const { data } = await api.get(`/bios/${bio.id}/current`);
      setCurrent(data as IgProfile);
    } catch {
      setCurrent(null);
    } finally {
      setLoadingCurrent(false);
    }
  }

  async function deleteConfig() {
    if (!bio || !confirm("Delete this profile config? (Stored values are lost; Instagram is untouched.)")) return;
    try {
      await api.delete(`/bios/${bio.id}`);
      setBio(null);
      toast("success", "Profile config deleted");
    } catch {
      setOpError("Delete failed");
    }
  }

  const busy = (s: string) => applyBusy === s;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Profile editor</h1>
      <p className="text-sm text-zinc-500">
        Pick an account, edit any section, Apply it — each section works on its own.
        Empty sections are never touched on Instagram.
      </p>
      <Card>
        <Field label="Account">
          <select className="input w-full max-w-full" value={accountId} onChange={(e) => selectAccount(e.target.value)}>
            <option value="">Select…</option>
            {((accounts ?? []) as Account[]).map((a) => <option key={a.id} value={a.id}>@{a.username}</option>)}
          </select>
        </Field>
      </Card>
      {opError && <p className="break-words text-sm text-red-500">{opError}</p>}
      {loading ? <Spinner /> : bio ? (
        <>
          <p className="text-xs text-zinc-500">
            Last applied {timeAgo(bio.last_applied ?? null)}
            {" · "}
            <button className="text-sky-500 hover:underline" disabled={loadingCurrent} onClick={loadCurrent}>
              {loadingCurrent ? "Reading…" : "Compare live"}
            </button>
          </p>
          {current ? (
            <div className="min-w-0 rounded bg-zinc-100 p-2 text-xs dark:bg-zinc-800">
              <p className="truncate font-semibold" title={current?.username}>Live on Instagram @{current?.username} ({current?.follower_count ?? "—"} followers):</p>
              <p className="break-words">{current?.full_name} {current?.is_private ? "🔒" : ""}</p>
              <p className="whitespace-pre-wrap break-words">{current?.biography}</p>
              {current?.external_url && <p className="break-all">{current?.external_url}</p>}
            </div>
          ) : current === null ? (
            <p className="text-xs text-red-500">Could not read live profile (session/proxy issue).</p>
          ) : null}
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardTitle>Bio text</CardTitle>
              <Field label="Biography">
                <textarea className="input" rows={3} value={dText} onChange={(e) => setDText(e.target.value)} placeholder="Empty = leave untouched" />
              </Field>
              <button className="btn-primary mt-2 !py-1.5 text-xs" disabled={busy("bio")} onClick={() => saveAndApply("bio", { text: dText })}>
                {busy("bio") ? "Applying…" : "Apply bio"}
              </button>
            </Card>
            <Card>
              <CardTitle>Link</CardTitle>
              <Field label="External URL">
                <input className="input" value={dLink} onChange={(e) => setDLink(e.target.value)} placeholder="https://t.me/… (empty = leave untouched)" />
              </Field>
              <button className="btn-primary mt-2 !py-1.5 text-xs" disabled={busy("link")} onClick={() => saveAndApply("link", { link_url: dLink })}>
                {busy("link") ? "Applying…" : "Apply link"}
              </button>
            </Card>
            <Card>
              <CardTitle>Full name</CardTitle>
              <Field label="Display name">
                <input className="input" value={dName} onChange={(e) => setDName(e.target.value)} placeholder="Empty = leave untouched" />
              </Field>
              <button className="btn-primary mt-2 !py-1.5 text-xs" disabled={busy("full_name")} onClick={() => saveAndApply("full_name", { full_name: dName })}>
                {busy("full_name") ? "Applying…" : "Apply name"}
              </button>
            </Card>
            <Card>
              <CardTitle>Profile picture</CardTitle>
              <p className="text-xs text-zinc-500">Stored: {bio.has_picture ? "set" : "none"}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <label className="btn-ghost cursor-pointer !py-1.5 text-xs">
                  {picBusy ? "Uploading…" : bio.has_picture ? "Replace pic" : "Upload pic"}
                  <input type="file" className="hidden" accept="image/*" onChange={(e) => uploadPicture(e.target.files?.[0] ?? null)} />
                </label>
                {bio.has_picture && (
                  <button className="btn-ghost !py-1.5 text-xs text-red-500" disabled={picBusy} onClick={deletePicture}>
                    Remove pic
                  </button>
                )}
                <button className="btn-primary !py-1.5 text-xs" disabled={!bio.has_picture || busy("picture")} onClick={() => saveAndApply("picture", {})}>
                  {busy("picture") ? "Applying…" : "Apply picture"}
                </button>
                <button className="btn-ghost !py-1.5 text-xs !text-red-500" disabled={busy("remove-live")} onClick={removeLivePicture} title="Delete the current Instagram profile photo (one-way)">
                  {busy("remove-live") ? "Removing…" : "Remove live photo"}
                </button>
              </div>
            </Card>
            <Card>
              <CardTitle>Privacy</CardTitle>
              <div className="flex flex-wrap gap-2">
                {(["", "private", "public"] as Privacy[]).map((p) => (
                  <button
                    key={p}
                    className={`btn-ghost !py-1.5 text-xs ${dPriv === p ? "!bg-sky-500/15 !text-sky-500" : ""}`}
                    onClick={() => setDPriv(p)}
                  >
                    {p === "" ? "Leave as-is" : p === "private" ? "🔒 Private" : "Public"}
                  </button>
                ))}
              </div>
              <button className="btn-primary mt-2 !py-1.5 text-xs" disabled={busy("privacy")} onClick={() => saveAndApply("privacy", { make_private: privToBody(dPriv) })}>
                {busy("privacy") ? "Applying…" : "Apply privacy"}
              </button>
            </Card>
          </div>
          <button className="text-xs text-red-500 hover:underline" onClick={deleteConfig}>Delete this profile config</button>
        </>
      ) : accountId ? null : (
        <p className="text-sm text-zinc-500">Select an account to edit its Instagram profile, section by section.</p>
      )}
    </div>
  );
}
