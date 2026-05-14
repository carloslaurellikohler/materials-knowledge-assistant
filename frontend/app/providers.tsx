"use client";

import type { ReactNode } from "react";

import { ClerkProvider } from "@clerk/nextjs";

import { isClerkEnabled } from "./lib/clerk";

export function Providers({ children }: { children: ReactNode }) {
  if (!isClerkEnabled) return <>{children}</>;
  return <ClerkProvider>{children}</ClerkProvider>;
}
