import { Database, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export function DocumentPanel({
  documents,
  onRefresh,
}: {
  documents: string[];
  onRefresh: () => Promise<void>;
}) {
  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Database className="h-4 w-4" />
          Indexed Documents
        </div>
        <Button onClick={() => void onRefresh()} size="sm" variant="secondary">
          <RefreshCcw className="h-4 w-4" />
          Refresh
        </Button>
      </CardHeader>
      <CardContent className="max-h-[65vh] overflow-auto">
        {documents.length === 0 ? (
          <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
            No documents loaded yet.
          </div>
        ) : (
          <ul className="space-y-2">
            {documents.map((doc) => (
              <li className="rounded-md border border-border bg-secondary/40 p-2 text-xs text-foreground" key={doc}>
                {doc}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

