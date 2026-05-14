"use client";

import { useEffect } from "react";

import { ChatComposer } from "@/components/chat/chat-composer";
import { ChatWindow } from "@/components/chat/chat-window";
import { DocumentPanel } from "@/components/chat/document-panel";
import { HeaderBar } from "@/components/layout/header-bar";
import { UploadPanel } from "@/components/upload/upload-panel";
import { useChatSession } from "@/hooks/use-chat-session";

function ChatWorkspace({ token }: { token: string | null }) {
  const session = useChatSession(token);

  useEffect(() => {
    if (token) {
      void session.loadDocuments();
    }
  }, [token, session]);

  return (
    <div className="min-h-screen bg-background">
      <HeaderBar />
      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-4 p-4 lg:grid-cols-[320px_1fr]">
        <section className="space-y-4">
          <DocumentPanel documents={session.documents} onRefresh={session.loadDocuments} />
          <UploadPanel onUpload={session.addUpload} uploads={session.uploads} />
        </section>
        <section className="grid gap-4 lg:grid-rows-[1fr_auto]">
          <ChatWindow messages={session.messages} />
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

export default function ChatPage() {
  return <ChatWorkspace token={null} />;
}
