"use client";
import { Card, CardTitle, QueryFailed, Spinner } from "@/components/ui";
import { useApiMutation, useSettings } from "@/hooks/use-api";
import type { Setting } from "@/types/models";

export default function SettingsPage() {
  const { data, isLoading, isError, refetch } = useSettings();
  const save = useApiMutation("put", [["settings"]], "Setting saved");
  const testIg = useApiMutation("post", []);
  const settings = (data ?? []) as Setting[];
  const groups = settings.reduce<Record<string, Setting[]>>((acc, s) => {
    (acc[s.category] ||= []).push(s);
    return acc;
  }, {});

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Global settings</h1>
      {isLoading ? <Spinner /> : isError ? <QueryFailed onRetry={() => refetch()} /> : Object.entries(groups).map(([cat, items]) => (
        <Card key={cat}>
          <CardTitle>{cat}</CardTitle>
          {items.map((s) => (
            <form
              key={s.key}
              className="flex flex-wrap items-center gap-2 border-t border-zinc-100 py-2 first:border-0 dark:border-zinc-800"
              onSubmit={(e) => {
                e.preventDefault();
                const fd = new FormData(e.target as HTMLFormElement);
                save.mutate({ url: `/settings/${s.key}`, body: { value: String(fd.get("value") ?? "") } });
              }}
            >
              <div className="min-w-0 flex-1">
                <p className="font-mono text-xs font-semibold">{s.key}</p>
                <p className="truncate text-xs text-zinc-500">{s.is_sensitive ? "(sensitive â€” masked)" : s.value || "(empty)"}</p>
              </div>
              <input name="value" className="input min-w-[140px] flex-1 sm:flex-none sm:!w-48" placeholder="new value" />
              <button className="btn-ghost !px-3 !py-1.5 text-xs" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save"}</button>
            </form>
          ))}
        </Card>
      ))}
      <Card>
        <CardTitle>Connection tests</CardTitle>
        <div className="flex gap-2">
          <button className="btn-ghost flex-1" disabled={testIg.isPending} onClick={() => testIg.mutate({ url: "/settings/test-instagram" })}>{testIg.isPending ? "Testing…" : "Test Instagram"}</button>
        </div>
        {testIg.data && (
          <pre className="mt-2 overflow-auto rounded bg-zinc-100 p-2 text-xs dark:bg-zinc-800">{JSON.stringify(testIg.data, null, 2)}</pre>
        )}
      </Card>
    </div>
  );
}
