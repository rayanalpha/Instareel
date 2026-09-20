"use client";
import { Clapperboard, Heart, PlusSquare, User } from "lucide-react";

export type PhoneTab = "profile" | "reels" | "composer" | "activity";

const TABS: { id: PhoneTab; icon: typeof User; label: string }[] = [
  { id: "profile", icon: User, label: "Profile" },
  { id: "reels", icon: Clapperboard, label: "Reels" },
  { id: "composer", icon: PlusSquare, label: "New" },
  { id: "activity", icon: Heart, label: "Activity" },
];

export function PhoneTabs({ tab, onChange }: { tab: PhoneTab; onChange: (t: PhoneTab) => void }) {
  return (
    <div className="flex items-center justify-around border-t border-zinc-200 bg-white py-2 dark:border-zinc-800 dark:bg-black">
      {TABS.map(({ id, icon: Icon, label }) => (
        <button
          key={id}
          aria-label={label}
          onClick={() => onChange(id)}
          className={`p-1.5 ${tab === id ? "text-zinc-900 dark:text-white" : "text-zinc-400"}`}
        >
          <Icon className="h-6 w-6" />
        </button>
      ))}
    </div>
  );
}
