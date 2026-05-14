import { Citation } from "@/types/chat";
import { Badge } from "@/components/ui/badge";

export function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;

  return (
    <div className="mt-3 space-y-2">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">References</div>
      <ul className="space-y-2">
        {citations.map((citation, index) => (
          <li className="rounded-md border border-border bg-secondary/50 p-2 text-xs text-foreground" key={`${citation.source}-${index}`}>
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <Badge>{citation.source}</Badge>
              {citation.page ? <Badge>p. {citation.page}</Badge> : null}
            </div>
            <p className="line-clamp-3 text-muted-foreground">{citation.excerpt}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

