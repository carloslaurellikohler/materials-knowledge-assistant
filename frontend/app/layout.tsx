import "./globals.css";
import type { ReactNode } from "react";
import { isClerkEnabled } from "./lib/clerk";

export default function RootLayout({ children }: { children: ReactNode }) {
  const bodyContent = (() => {
    if (!isClerkEnabled) {
      return children;
    }

    const { ClerkProvider } = require("@clerk/nextjs");
    return <ClerkProvider>{children}</ClerkProvider>;
  })();

  return (
    <html lang="en">
      <body>{bodyContent}</body>
    </html>
  );
}
