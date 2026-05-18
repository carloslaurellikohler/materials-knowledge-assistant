"use client";

import { useRef, useState } from "react";

import { FileText, Trash2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/documents/status-badge";
import { UserDocument } from "@/types/chat";

const MAX_PDF_MB = 100;
const BYTES_PER_MB = 1024 * 1024;

function formatSize(bytes: number): string {
  if (bytes < BYTES_PER_MB) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / BYTES_PER_MB).toFixed(1)} MB`;
}

export function DocumentManager({
  documents,
  onUpload,
  onDelete,
}: {
  documents: UserDocument[];
  onUpload: (file: File) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      setLocalError("Apenas arquivos PDF são aceitos.");
      return;
    }
    if (file.size > MAX_PDF_MB * BYTES_PER_MB) {
      setLocalError(`O arquivo excede o limite de ${MAX_PDF_MB} MB.`);
      return;
    }
    setLocalError(null);
    setUploading(true);
    try {
      await onUpload(file);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void handleFile(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) void handleFile(file);
  };

  const handleDelete = async (doc: UserDocument) => {
    if (!confirm(`Remover "${doc.original_filename}" e todos os seus vetores? Esta ação não pode ser desfeita.`)) return;
    await onDelete(doc.id);
  };

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <FileText className="h-4 w-4" />
          Minha Base de Conhecimento
        </div>
        <span className="text-xs text-muted-foreground">{documents.length} doc{documents.length !== 1 ? "s" : ""}</span>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Drop zone */}
        <div
          className={`rounded-md border-2 border-dashed p-4 text-center transition-colors ${
            dragging
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50 hover:bg-secondary/30"
          } ${uploading ? "pointer-events-none opacity-50" : "cursor-pointer"}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
        >
          <Upload className="mx-auto mb-1 h-5 w-5 text-muted-foreground" />
          <p className="text-xs text-muted-foreground">
            {uploading ? "Enviando…" : "Arraste um PDF ou clique para selecionar"}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground/60">Máx. {MAX_PDF_MB} MB</p>
        </div>
        <input
          ref={inputRef}
          accept=".pdf,application/pdf"
          className="hidden"
          type="file"
          onChange={handleInputChange}
        />

        {localError && (
          <p className="text-xs text-red-600">{localError}</p>
        )}

        {/* Document list */}
        {documents.length === 0 ? (
          <p className="rounded-md border border-dashed border-border p-3 text-center text-xs text-muted-foreground">
            Nenhum documento indexado ainda.
          </p>
        ) : (
          <ul className="max-h-[50vh] space-y-2 overflow-auto">
            {documents.map((doc) => (
              <li
                key={doc.id}
                className="rounded-md border border-border bg-secondary/40 p-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-foreground" title={doc.original_filename}>
                      {doc.original_filename}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <StatusBadge status={doc.indexing_status} />
                      {doc.chunk_count != null && (
                        <span className="text-xs text-muted-foreground">{doc.chunk_count} chunks</span>
                      )}
                      <span className="text-xs text-muted-foreground">{formatSize(doc.size)}</span>
                    </div>
                    {doc.indexing_status === "error" && doc.indexing_error && (
                      <p className="mt-1 truncate text-xs text-red-600" title={doc.indexing_error}>
                        {doc.indexing_error}
                      </p>
                    )}
                  </div>
                  <Button
                    className="h-6 w-6 shrink-0 text-muted-foreground hover:text-red-600"
                    size="sm"
                    variant="ghost"
                    onClick={() => void handleDelete(doc)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
