"use client";
import { useRouter } from "next/navigation";
import type { Account } from "@/types/models";

export function AccountSwitcher({
  accounts,
  currentId,
  onPick,
}: {
  accounts: Account[];
  currentId: number | null;
  onPick: (id: number) => void;
}) {
  const router = useRouter();
  if (accounts.length === 0) return null;
  // Always visible: with a single account it shows the current one plus an
  // add button, so the switcher is discoverable before a 2nd account exists.
  return (
    <div className="flex items-center gap-2 overflow-x-auto border-b border-zinc-200 px-3 py-2 dark:border-zinc-800">
      {accounts.map((a) => {
        const active = a.id === currentId;
        return (
          <button
            key={a.id}
            onClick={() => onPick(a.id)}
            title={`@${a.username}`}
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
              active
                ? "bg-gradient-to-tr from-amber-400 via-pink-500 to-violet-500 text-white"
                : "bg-zinc-200 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300"
            }`}
          >
            {active ? (
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white text-[11px] text-zinc-900 dark:bg-black dark:text-white">
                {a.username.slice(0, 2).toUpperCase()}
              </span>
            ) : (
              a.username.slice(0, 2).toUpperCase()
            )}
          </button>
        );
      })}
      <button
        onClick={() => router.push("/dashboard/accounts")}
        title="Add account"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 border-dashed border-zinc-300 text-lg text-zinc-400 dark:border-zinc-700"
      >
        +
      </button>
    </div>
  );
}
