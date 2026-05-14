"use client";

import { LogOut } from "lucide-react";

import { isClerkEnabled } from "@/app/lib/clerk";
import { Button } from "@/components/ui/button";

export function HeaderBar() {
  return (
    <header className="border-b border-border bg-white">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        <div>
          <h1 className="text-sm font-semibold tracking-tight text-foreground">Materials Knowledge Assistant</h1>
          <p className="text-xs text-muted-foreground">Closed corpus engineering workspace</p>
        </div>
        <div className="flex items-center gap-3">
          {isClerkEnabled ? <AuthActions /> : null}
        </div>
      </div>
    </header>
  );
}

function AuthActions() {
  const { SignOutButton, UserButton } = require("@clerk/nextjs");

  return (
    <>
      <UserButton afterSignOutUrl="/sign-in" />
      <SignOutButton redirectUrl="/sign-in">
        <Button size="sm" variant="ghost">
          <LogOut className="h-4 w-4" />
          Sign out
        </Button>
      </SignOutButton>
    </>
  );
}
