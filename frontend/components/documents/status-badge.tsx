import { DocumentStatus } from "@/types/chat";

const STATUS_CONFIG: Record<DocumentStatus, { label: string; className: string }> = {
  pending: {
    label: "Aguardando",
    className: "bg-muted text-muted-foreground",
  },
  processing: {
    label: "Processando",
    className: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  },
  chunking: {
    label: "Dividindo",
    className: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  },
  embedding: {
    label: "Gerando embeddings",
    className: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  },
  indexed: {
    label: "Indexado",
    className: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  },
  error: {
    label: "Erro",
    className: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  },
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${config.className}`}
    >
      {config.label}
    </span>
  );
}
