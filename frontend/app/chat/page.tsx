"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";

import { useAuth } from "@clerk/nextjs";

import { ChatComposer } from "@/components/chat/chat-composer";
import { ChatWindow } from "@/components/chat/chat-window";
import { DocumentPanel } from "@/components/chat/document-panel";
import { HeaderBar } from "@/components/layout/header-bar";
import { UploadPanel } from "@/components/upload/upload-panel";
import { useChatSession } from "@/hooks/use-chat-session";
import { isClerkEnabled } from "@/app/lib/clerk";

function ChatWorkspace({ token }: { token: string | null }) {
  const session = useChatSession(token);

  useEffect(() => {
    if (token) {
      void session.loadDocuments();
    }
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen bg-background">
      <HeaderBar />
      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-4 p-4 lg:grid-cols-[320px_1fr]">
        <section className="space-y-4">
          <DocumentPanel documents={session.documents} onRefresh={session.loadDocuments} />
          <UploadPanel onUpload={session.addUpload} uploads={session.uploads} />
        </section>
        <section className="grid gap-4 lg:grid-rows-[1fr_auto]">
          <ChatWindow messages={session.messages} onClear={session.clearSession} />
          <ChatComposer
            disabled={!session.canSend}
            error={session.error}
            onChange={session.setInput}
            onSubmit={session.sendMessage}
            value={session.input}
          />
        </section>
      </main>
    </div>
  );
}

function ClerkChatPage() {
  const { isLoaded, getToken } = useAuth();
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoaded) return;
    const load = async () => {
      const t = await getToken();
      setToken(t);
    };
    void load();
    const interval = setInterval(() => {
      void load();
    }, 50_000);
    return () => clearInterval(interval);
  }, [isLoaded, getToken]);

  return <ChatWorkspace token={token} />;
}

export default function ChatPage() {
  if (isClerkEnabled) {
    return <ClerkChatPage />;
  }
  return <ChatWorkspace token={null} />;
}
