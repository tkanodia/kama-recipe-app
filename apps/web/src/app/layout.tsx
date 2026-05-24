import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import "./globals.css";
import { isClerkEnabled } from "@/lib/clerk";
import { Providers } from "./providers";
import { Shell } from "./shell";

export const metadata: Metadata = {
  title: "Kama",
  description: "AI recipe workspace",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const clerkOn = isClerkEnabled();

  const inner = (
    <Providers>
      <Shell clerkEnabled={clerkOn}>{children}</Shell>
    </Providers>
  );

  if (!clerkOn) {
    return (
      <html lang="en">
        <body>{inner}</body>
      </html>
    );
  }

  return (
    <ClerkProvider>
      <html lang="en">
        <body>{inner}</body>
      </html>
    </ClerkProvider>
  );
}
