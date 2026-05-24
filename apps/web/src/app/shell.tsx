"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";
import type { ReactNode } from "react";

const NAV_ITEMS = [
  { href: "/recipes", label: "Recipes" },
  { href: "/search", label: "Search" },
  { href: "/ask", label: "Ask" },
  { href: "/create", label: "Create" },
  { href: "/pantry", label: "Pantry" },
  { href: "/ingest", label: "Ingest" },
] as const;

export function Shell({
  children,
  clerkEnabled,
}: {
  children: ReactNode;
  clerkEnabled: boolean;
}) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-kama-border bg-kama-surface px-6 py-3 flex items-center justify-between gap-4">
        <nav className="flex gap-6 text-sm">
          {NAV_ITEMS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={
                pathname.startsWith(href)
                  ? "text-white font-medium"
                  : "text-stone-200 hover:text-white"
              }
            >
              {label}
            </Link>
          ))}
        </nav>
        <div>
          {clerkEnabled && (
            <>
              <SignedOut>
                <SignInButton mode="modal">
                  <button
                    type="button"
                    className="rounded-md bg-orange-600 px-3 py-1.5 text-sm text-white hover:bg-orange-500"
                  >
                    Sign in
                  </button>
                </SignInButton>
              </SignedOut>
              <SignedIn>
                <UserButton afterSignOutUrl="/" />
              </SignedIn>
            </>
          )}
        </div>
      </header>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
