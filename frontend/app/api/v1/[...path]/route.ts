import { type NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

async function proxy(req: NextRequest, path: string[]): Promise<Response> {
  const target = `${BACKEND}/api/v1/${path.join("/")}`;

  const headers = new Headers(req.headers);
  // Remove hop-by-hop headers that should not be forwarded
  headers.delete("host");

  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body: req.method !== "GET" && req.method !== "HEAD" ? req.body : undefined,
    cache: "no-store",
    // @ts-ignore — duplex required for streaming request body in Node.js fetch
    duplex: "half",
  });

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: upstream.headers,
  });
}

export const GET = (req: NextRequest, { params }: { params: { path: string[] } }) =>
  proxy(req, params.path);

export const POST = (req: NextRequest, { params }: { params: { path: string[] } }) =>
  proxy(req, params.path);

export const PUT = (req: NextRequest, { params }: { params: { path: string[] } }) =>
  proxy(req, params.path);

export const PATCH = (req: NextRequest, { params }: { params: { path: string[] } }) =>
  proxy(req, params.path);

export const DELETE = (req: NextRequest, { params }: { params: { path: string[] } }) =>
  proxy(req, params.path);
