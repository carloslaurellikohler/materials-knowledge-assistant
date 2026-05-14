"use client";

import { FormEvent } from "react";
import { Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  disabled,
  error,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => Promise<void>;
  disabled: boolean;
  error: string | null;
}) {
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit();
  }

  return (
    <Card>
      <CardHeader className="text-sm font-semibold text-foreground">Prompt</CardHeader>
      <CardContent>
        <form className="space-y-3" onSubmit={submit}>
          <Textarea onChange={(event) => onChange(event.target.value)} placeholder="Ask about materials behavior, corrosion, testing, or standards..." value={value} />
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          <div className="flex justify-end">
            <Button disabled={disabled} type="submit">
              <Send className="h-4 w-4" />
              {disabled ? "Streaming..." : "Send"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

