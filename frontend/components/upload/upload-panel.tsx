"use client";

import { useRef } from "react";
import { FileAudio, ImageUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { UploadItem } from "@/types/chat";

function statusLabel(status: UploadItem["status"]) {
  if (status === "queued") return "Queued";
  if (status === "uploading") return "Uploading";
  if (status === "processing") return "Processing";
  if (status === "success") return "Ready";
  return "Error";
}

export function UploadPanel({
  uploads,
  onUpload,
}: {
  uploads: UploadItem[];
  onUpload: (file: File, type: "image" | "audio") => Promise<void>;
}) {
  const imageInputRef = useRef<HTMLInputElement>(null);
  const audioInputRef = useRef<HTMLInputElement>(null);

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Multimodal Uploads</h2>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <input
            ref={imageInputRef}
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            type="file"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void onUpload(file, "image");
              event.currentTarget.value = "";
            }}
          />
          <Button size="sm" variant="secondary" onClick={() => imageInputRef.current?.click()}>
            <ImageUp className="mr-1 h-4 w-4" />
            Upload image
          </Button>

          <input
            ref={audioInputRef}
            accept="audio/mpeg,audio/wav,audio/mp4,audio/x-m4a"
            className="hidden"
            type="file"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void onUpload(file, "audio");
              event.currentTarget.value = "";
            }}
          />
          <Button size="sm" variant="secondary" onClick={() => audioInputRef.current?.click()}>
            <FileAudio className="mr-1 h-4 w-4" />
            Upload audio
          </Button>
        </div>

        {uploads.length > 0 ? (
          <ul className="space-y-2">
            {uploads.map((upload) => (
              <li className="rounded-md border border-border p-2 text-xs" key={upload.id}>
                <div className="font-medium text-foreground">{upload.filename}</div>
                <div className="text-muted-foreground">{statusLabel(upload.status)}</div>
                {upload.error ? <div className="text-red-600">{upload.error}</div> : null}
                {upload.result ? (
                  <div className="mt-1 line-clamp-3 text-xs text-muted-foreground">{upload.result}</div>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
            Upload image/audio files to enrich prompts in the current session.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
