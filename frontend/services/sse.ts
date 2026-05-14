import { Citation, SseEvent } from "@/types/chat";

export async function* parseSseStream(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<SseEvent, void, unknown> {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";

    for (const block of blocks) {
      const lines = block.split("\n");
      const event = lines.find((line) => line.startsWith("event:"))?.replace("event:", "").trim();
      const data = lines.find((line) => line.startsWith("data:"))?.replace("data:", "").trim() ?? "";
      if (!event) continue;
      if (event === "token") yield { event: "token", data };
      if (event === "done") yield { event: "done", data };
      if (event === "error") yield { event: "error", data };
      if (event === "citations") {
        try {
          yield { event: "citations", data: JSON.parse(data) as Citation[] };
        } catch {
          yield { event: "citations", data: [] };
        }
      }
    }
  }
}

