"use client";
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
  if (accounts.length <= 1) return null;
  return (
    <div className="flex gap-2 overflow-x-auto border-b border-zinc-200 px-3 py-2 dark:border-zinc-800">
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
    </div>
  );
}
