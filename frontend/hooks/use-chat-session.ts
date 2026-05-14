"use client";

import { useCallback, useMemo, useState } from "react";

import { fetchDocuments, streamChat, uploadAttachment } from "@/services/api";
import { ChatMessage, Citation, UploadItem } from "@/types/chat";

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

const MAX_IMAGE_SIZE = 20 * 1024 * 1024;
const MAX_AUDIO_SIZE = 40 * 1024 * 1024;

export function useChatSession(token: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [documents, setDocuments] = useState<string[]>([]);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSend = useMemo(() => !!token && input.trim().length > 0 && !isStreaming, [token, input, isStreaming]);

  const loadDocuments = useCallback(async () => {
    if (!token) return;
    setError(null);
    try {
      const items = await fetchDocuments(token);
      setDocuments(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load documents");
    }
  }, [token]);

  const sendMessage = useCallback(async () => {
    if (!token || !canSend) return;
    setError(null);
    const message = input.trim();
    setInput("");

    const userMsg: ChatMessage = { id: uid(), role: "user", text: message, createdAt: Date.now() };
    const assistantId = uid();
    setMessages((prev) => [
      ...prev,
      userMsg,
      { id: assistantId, role: "assistant", text: "", createdAt: Date.now(), status: "streaming" },
    ]);
    setIsStreaming(true);

    let citations: Citation[] = [];
    try {
      await streamChat(token, message, {}, {
        onToken: (tokenChunk) => {
          setMessages((prev) =>
            prev.map((msg) => (msg.id === assistantId ? { ...msg, text: msg.text + tokenChunk } : msg)),
          );
        },
        onCitations: (items) => {
          citations = items;
        },
        onDone: () => {
          setMessages((prev) =>
            prev.map((msg) => (msg.id === assistantId ? { ...msg, citations, status: "done" } : msg)),
          );
        },
        onError: (messageText) => {
          setMessages((prev) =>
            prev.map((msg) => (msg.id === assistantId ? { ...msg, status: "error" } : msg)),
          );
          setError(messageText || "Streaming failed");
        },
      });
    } catch (err) {
      setMessages((prev) => prev.map((msg) => (msg.id === assistantId ? { ...msg, status: "error" } : msg)));
      setError(err instanceof Error ? err.message : "Failed to send message");
    } finally {
      setIsStreaming(false);
    }
  }, [token, canSend, input]);

  const addUpload = useCallback(
    async (file: File, type: "image" | "audio") => {
      if (!token) return;
      const id = uid();
      const limit = type === "image" ? MAX_IMAGE_SIZE : MAX_AUDIO_SIZE;
      if (file.size > limit) {
        setUploads((prev) => [...prev, { id, filename: file.name, type, status: "error", error: "File too large" }]);
        return;
      }
      setUploads((prev) => [...prev, { id, filename: file.name, type, status: "queued" }]);
      try {
        setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, status: "uploading" } : u)));
        await uploadAttachment(token, file, type);
        setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, status: "processing" } : u)));
        setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, status: "success" } : u)));
      } catch (err) {
        setUploads((prev) =>
          prev.map((u) =>
            u.id === id ? { ...u, status: "error", error: err instanceof Error ? err.message : "Upload failed" } : u,
          ),
        );
      }
    },
    [token],
  );

  return {
    messages,
    documents,
    uploads,
    input,
    setInput,
    canSend,
    isStreaming,
    error,
    sendMessage,
    loadDocuments,
    addUpload,
  };
}

