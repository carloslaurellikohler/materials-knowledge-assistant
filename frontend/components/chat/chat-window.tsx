"use client";

import { useEffect, useRef } from "react";

import { Trash2 } from "lucide-react";

import { CitationList } from "@/components/citations/citation-list";
import { MarkdownRenderer } from "@/components/markdown/markdown-renderer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChatMessage } from "@/types/chat";

export function ChatWindow({
  messages,
  onClear,
}: {
  messages: ChatMessage[];
  onClear: () => void;
}) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between text-sm font-semibold text-foreground">
        <span>Conversa</span>
        {messages.length > 0 ? (
          <Button onClick={onClear} size="sm" variant="ghost">
            <Trash2 className="mr-1 h-4 w-4" />
            Limpar
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="max-h-[65vh] space-y-4 overflow-x-hidden overflow-y-auto">
        {messages.length === 0 ? (
          <div className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">
            Inicie uma conversa com seu acervo de engenharia indexado.
          </div>
        ) : null}
        {messages.map((msg) => (
          <article className="min-w-0 break-words rounded-md border border-border p-3" key={msg.id}>
            <div className="mb-2 flex items-center gap-2">
              <Badge>{msg.role === "user" ? "Você" : "Assistente"}</Badge>
              {msg.status ? (
                <span className="text-xs text-muted-foreground">
                  {msg.status === "streaming" ? "gerando…" : msg.status === "error" ? "erro" : "concluído"}
                </span>
              ) : null}
            </div>
            {msg.role === "assistant" ? <MarkdownRenderer content={msg.text || "..."} /> : <p className="text-sm">{msg.text}</p>}
            {msg.citations ? <CitationList citations={msg.citations} /> : null}
          </article>
        ))}
        <div ref={bottomRef} />
      </CardContent>
    </Card>
  );
}
