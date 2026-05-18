# Frontend Specification (FES)
## Materials Knowledge Assistant (MKA)

Version: 2.0
Status: Aligned with current implementation
Author: Carlos Eduardo
Date: May 2026

---

# 1. Purpose

This document defines the frontend specification for the Materials Knowledge Assistant (MKA), reflecting the implementation as of May 2026.

The frontend delivers a modern, responsive, engineering-oriented user experience focused on:

- Conversational AI interaction with streaming
- Per-user document management (upload, status polling, delete)
- Citation visualization
- Technical readability (markdown + typography)
- Multimodal interaction (image, audio)
- Transparent backend proxying via Next.js API route

---

# 2. Frontend Technology Stack

| Layer | Technology / Version |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript 5.5 |
| Styling | TailwindCSS 3.4 + `@tailwindcss/typography` |
| UI Components | shadcn/ui patterns (Button, Card, Badge, Textarea) |
| Markdown rendering | `react-markdown` |
| Icons | `lucide-react` |
| Authentication | `@clerk/nextjs` (optional via `NEXT_PUBLIC_ENABLE_CLERK`) |
| State Management | React Context + Hooks (custom `useChatSession`) |
| API Communication | REST + Server-Sent Events (via internal proxy) |
| Hosting | Docker container (Next.js standalone) |
| Class utilities | `class-variance-authority`, `clsx`, `tailwind-merge` |

---

# 3. Frontend Architectural Principles

The frontend implementation prioritizes:

- Technical readability (typography-tuned for engineering text)
- Minimal cognitive load
- Responsive layouts
- Streaming-first UX (SSE)
- Modular UI components
- Accessibility
- Fast rendering
- Engineering-oriented interaction
- Portuguese (pt-BR) as primary locale

---

# 4. Project Structure

```text
frontend/
│
├── app/                                # Next.js App Router
│   ├── chat/page.tsx                   # main workspace (force-dynamic)
│   ├── sign-in/[[...sign-in]]/page.tsx # Clerk sign-in
│   ├── sign-up/[[...sign-up]]/page.tsx # Clerk sign-up
│   ├── api/v1/[...path]/route.ts       # transparent proxy to backend
│   ├── providers.tsx                   # conditional ClerkProvider
│   ├── lib/clerk.ts                    # isClerkEnabled flag
│   ├── layout.tsx                      # root layout (pt-BR locale)
│   └── page.tsx                        # redirect → /chat
│
├── components/
│   ├── chat/
│   │   ├── chat-window.tsx             # message history (markdown, citations)
│   │   ├── chat-composer.tsx           # input form
│   │   └── document-panel.tsx          # legacy doc list (kept for compatibility)
│   ├── citations/
│   │   └── citation-list.tsx
│   ├── documents/
│   │   ├── document-manager.tsx        # NEW: drag-drop upload, polling, delete
│   │   └── status-badge.tsx            # NEW: color-coded status indicator
│   ├── upload/
│   │   └── upload-panel.tsx            # image + audio attachments
│   ├── markdown/
│   │   └── markdown-renderer.tsx       # react-markdown wrapper with prose styling
│   ├── layout/
│   │   └── header-bar.tsx              # app header (Clerk UserButton when enabled)
│   └── ui/                             # Button, Card, Badge, Textarea
│
├── hooks/
│   └── use-chat-session.ts             # central state hook (see Section 13)
│
├── services/
│   ├── api.ts                          # REST calls (fetchDocuments, uploadDocument, ...)
│   └── sse.ts                          # async generator over SSE events
│
├── types/
│   └── chat.ts                         # Citation, ChatMessage, UploadItem, UserDocument, DocumentStatus, SseEvent
│
├── middleware.ts                       # Clerk auth (no-op when disabled)
├── next.config.mjs
├── tailwind.config.ts
├── postcss.config.js
├── tsconfig.json
└── package.json
```

The directory structure differs in two notable ways from V1.0 of this spec:
- `components/documents/` is new and carries the per-user document management UI.
- `app/api/v1/[...path]/route.ts` exists as a transparent proxy from the frontend origin to `BACKEND_URL`.

---

# 5. UI Architecture

## 5.1 Core UI Modules

| Module | Implementation |
|---|---|
| Auth Module | Clerk pages + `middleware.ts` + `app/providers.tsx` (conditional) |
| Chat Module | `chat-window.tsx`, `chat-composer.tsx`, `document-panel.tsx` |
| Document Management | `components/documents/document-manager.tsx`, `status-badge.tsx` |
| Multimodal Upload Module | `components/upload/upload-panel.tsx` |
| Citation Renderer | `components/citations/citation-list.tsx` |
| Markdown Renderer | `components/markdown/markdown-renderer.tsx` |
| Streaming Handler | `services/sse.ts` |
| Session Manager | `hooks/use-chat-session.ts` |

---

# 6. Authentication Flow

## 6.1 Authentication Strategy

Authentication uses Clerk (any provider Clerk supports: Google, email, etc.). The backend validates the Clerk JWT (RS256 via JWKS in production, HS256 fallback in dev/test).

The frontend can also operate **without Clerk**:

- When `NEXT_PUBLIC_ENABLE_CLERK=false`, `app/providers.tsx` does NOT wrap the tree with `ClerkProvider`.
- `middleware.ts` becomes a no-op, and routes are publicly accessible.
- This mode is intended for local development only.

## 6.2 Frontend Responsibilities

The frontend must (when Clerk is enabled):

- Redirect unauthenticated users to `/sign-in`
- Manage Clerk sessions
- Forward the bearer JWT on every protected request (handled inside `services/api.ts`)
- Protect private routes via `middleware.ts`

## 6.3 Routes

| Route | Public | Purpose |
|---|---|---|
| `/` | redirect | redirects to `/chat` |
| `/chat` | Protected (when Clerk on) | main workspace |
| `/sign-in/*` | Public | Clerk sign-in |
| `/sign-up/*` | Public | Clerk sign-up |
| `/api/v1/*` | Pass-through | transparent proxy to backend |

---

# 7. Chat Interface Specification

## 7.1 Chat Goals

The chat experience provides:

- Real-time interaction (SSE)
- Streaming AI responses
- Markdown rendering of assistant messages
- Citation rendering alongside each assistant message
- Mobile responsiveness

## 7.2 Chat Layout

```text
+-----------------------------------+
| HeaderBar (UserButton if Clerk on)|
+----------------+------------------+
| DocumentManager| ChatWindow       |
| (drag-drop,    | (messages +      |
|  status,       |  citations)      |
|  delete)       |                  |
|                |                  |
|                +------------------+
|                | ChatComposer     |
|                | (input + submit) |
|                +------------------+
| UploadPanel    |                  |
| (image/audio)  |                  |
+----------------+------------------+
```

## 7.3 Message Types

| Type | Description |
|---|---|
| User message | User-generated prompt |
| Assistant message | Generated response (markdown-rendered) |
| Status badge on message | "gerando" / "concluído" / "erro" |
| Citation block | Source references (rendered by `CitationList`) |
| Upload status | File processing state (`StatusBadge` for documents; status text for image/audio) |
| Error message | Inline error display |

---

# 8. Streaming UX Specification

## 8.1 Streaming Goals

The interface:

- Displays tokens incrementally
- Reduces perceived latency
- Avoids layout shifting
- Preserves scroll behavior (auto-scroll to bottom on streaming)

## 8.2 Streaming Strategy

Streaming uses Server-Sent Events. The parser in `services/sse.ts` is an async generator that yields typed events:

```typescript
type SseEvent =
  | { event: "token"; data: string }
  | { event: "citations"; data: Citation[] }
  | { event: "done"; data: string }
  | { event: "error"; data: string };
```

Tokens are appended to the in-progress assistant message; on `citations`, the citation list is attached; on `done`, the message's status flips to `"done"`.

---

# 9. Document Management Specification

This is the primary surface for the user's knowledge base.

## 9.1 Component

`frontend/components/documents/document-manager.tsx` — props: `{ documents, onUpload, onDelete }`.

## 9.2 Features

- Drag-and-drop PDF upload (file input fallback)
- PDF validation (MIME and size)
- Document count, file size, chunk count, status visualization
- Indexing error display (when `indexing_status = "error"`)
- Delete with confirmation dialog
- Max file size: 100 MB (must match backend `MAX_UPLOAD_MB`)

## 9.3 Status Polling

The hook `useChatSession` polls `GET /api/v1/documents` every **3 seconds** while at least one document is in a non-terminal status. Terminal statuses are:

```typescript
const TERMINAL_STATUSES = ["indexed", "error"];
```

The status badge renders color-coded indicators for each state (`pending`, `processing`, `chunking`, `embedding`, `indexed`, `error`).

## 9.4 Endpoints Consumed

| Action | HTTP | Endpoint |
|---|---|---|
| List | `GET` | `/api/v1/documents` |
| Upload | `POST` | `/api/v1/documents` (multipart) |
| Delete | `DELETE` | `/api/v1/documents/{id}` |
| Poll | `GET` | `/api/v1/documents` (re-fetched periodically) |

---

# 10. Multimodal Upload Specification

`frontend/components/upload/upload-panel.tsx` — props: `{ uploads, onUpload }`.

## 10.1 Supported Uploads

| Type | Endpoint | Result |
|---|---|---|
| Image (PNG, JPG, WebP) | `POST /api/v1/upload/image` | textual description (GPT-4o) |
| Audio (MP3, WAV, M4A) | `POST /api/v1/upload/audio` | transcript (Whisper) |

Frontend size limits (must align with backend):
- Image: `MAX_IMAGE_SIZE = 20 MB`
- Audio: `MAX_AUDIO_SIZE = 40 MB`

> Note: the audio limit on the frontend (40 MB) exceeds the backend default (`MAX_AUDIO_UPLOAD_MB=25`). In production, configure both consistently.

## 10.2 UX Requirements

- Upload status indicator (`"Na fila" → "Enviando" → "Processando" → "Pronto" | "Erro"`)
- Show result inline (description for images, transcript for audio)
- The user can copy the textual result into the chat composer for further questions

---

# 11. Citation Rendering Specification

## 11.1 Component

`frontend/components/citations/citation-list.tsx`

## 11.2 Citation Shape (from backend)

```typescript
type Citation = {
  source: string;
  chapter?: string | null;
  section?: string | null;
  page?: number | null;
  excerpt: string;
};
```

## 11.3 Rendered Fields

Each citation displays:

- Source document filename
- Chapter / section (when available)
- Page number (when available)
- Excerpt preview (line-clamped)

---

# 12. Markdown Rendering Specification

## 12.1 Component

`frontend/components/markdown/markdown-renderer.tsx` (wraps `react-markdown`).

## 12.2 Supported Features

| Feature | Support |
|---|---|
| Headings | Yes |
| Lists | Yes |
| Tables | Yes |
| Code Blocks | Yes |
| Inline Code | Yes |
| Blockquotes | Yes |

Styling is provided by `@tailwindcss/typography` (the `prose` plugin).

## 12.3 Rendering Goals

- Technical readability
- Clean typography
- Proper spacing
- Mobile responsiveness

---

# 13. State Management Specification

## 13.1 Central Hook

`frontend/hooks/use-chat-session.ts` is the single source of truth for application state.

## 13.2 State Domains

| Domain | Variables | Purpose |
|---|---|---|
| Chat | `messages: ChatMessage[]`, `input: string`, `isStreaming: boolean` | Active conversation |
| Documents | `documents: UserDocument[]` | User's knowledge base (polled) |
| Uploads | `uploads: UploadItem[]` | Image/audio attachments in progress |
| Errors | `error: string \| null` | UI error display |

## 13.3 Operations

| Function | Behavior |
|---|---|
| `loadDocuments()` | `GET /api/v1/documents` and update state |
| `sendMessage()` | `POST /api/v1/chat` (SSE), stream tokens, attach citations |
| `addUpload(file, type)` | Upload image or audio attachment |
| `uploadPdf(file)` | `POST /api/v1/documents`, kick off polling |
| `removePdf(id)` | `DELETE /api/v1/documents/{id}` |
| `clearSession()` | Reset in-memory state |

## 13.4 Polling Loop

The hook starts a polling loop while any document is non-terminal:

```typescript
const POLL_INTERVAL_MS = 3000;
const TERMINAL_STATUSES = ["indexed", "error"];
```

The loop stops automatically when all documents reach a terminal status.

## 13.5 Constraints

| Constant | Value | Notes |
|---|---|---|
| `MAX_PDF_SIZE` | 100 MB | aligned with backend `MAX_UPLOAD_MB` |
| `MAX_IMAGE_SIZE` | 20 MB | aligned with backend `MAX_IMAGE_UPLOAD_MB` |
| `MAX_AUDIO_SIZE` | 40 MB | front-only — backend default is 25 MB (see §10) |

---

# 14. API Communication Specification

## 14.1 Communication Strategy

All backend interaction goes through `frontend/services/api.ts`. The base URL is the **same origin** as the frontend (`/api/v1`), because `frontend/app/api/v1/[...path]/route.ts` proxies every call to `BACKEND_URL` (default `http://localhost:8000` or `http://backend:8000` in Docker).

## 14.2 API Layer (`services/api.ts`)

| Function | Method | Endpoint | Purpose |
|---|---|---|---|
| `fetchDocuments(token)` | GET | `/api/v1/documents` | List user's documents |
| `uploadDocument(token, file)` | POST | `/api/v1/documents` | Upload PDF (multipart) |
| `deleteDocument(token, id)` | DELETE | `/api/v1/documents/{id}` | Delete document |
| `streamChat(token, message, metadata_filters, handlers)` | POST | `/api/v1/chat` | Stream SSE with handlers (`onToken`, `onCitations`, `onDone`, `onError`) |
| `uploadAttachment(token, file, type)` | POST | `/api/v1/upload/{type}` | Image or audio (type ∈ {image, audio}) |

## 14.3 SSE Parser (`services/sse.ts`)

`parseSseStream(stream)` is an async generator that yields typed `SseEvent` objects. It handles:

- `token` events — partial answer text
- `citations` events — JSON-parsed `Citation[]`
- `done` events — sentinel
- `error` events — error message

## 14.4 Request Headers

Protected requests include:

```text
Authorization: Bearer <Clerk JWT>
```

When Clerk is disabled, the header is omitted and the backend's HS256 fallback authenticates against `CLERK_JWT_SECRET`.

---

# 15. Types Specification

`frontend/types/chat.ts`:

```typescript
type Citation = {
  source: string;
  chapter?: string | null;
  section?: string | null;
  page?: number | null;
  excerpt: string;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  createdAt: number;
  status?: "streaming" | "done" | "error";
};

type UploadItem = {
  id: string;
  filename: string;
  type: "image" | "audio";
  status: "queued" | "uploading" | "processing" | "success" | "error";
  error?: string;
  result?: string;
};

type DocumentStatus =
  | "pending" | "processing" | "chunking" | "embedding" | "indexed" | "error";

type UserDocument = {
  id: string;
  filename: string;
  original_filename: string;
  size: number;
  indexing_status: DocumentStatus;
  indexing_error?: string | null;
  chunk_count?: number | null;
  embedding_model?: string | null;
  qdrant_collection: string;
  created_at: string;
};

type SseEvent =
  | { event: "token"; data: string }
  | { event: "citations"; data: Citation[] }
  | { event: "done"; data: string }
  | { event: "error"; data: string };
```

These types mirror the backend Pydantic schemas (`backend/app/api/schemas/`).

---

# 16. Error Handling UX

## 16.1 UX Goals

- Human-readable errors
- Retry mechanisms (user-initiated)
- Graceful fallback states
- Stable rendering during failures

## 16.2 Example Error Messages

| Error | UI Message |
|---|---|
| Upload Failure | "Não foi possível enviar o arquivo." |
| Retrieval Failure / Empty Context | "A literatura técnica indexada não fornece evidência suficiente para responder a esta questão." (from backend fallback) |
| Indexing Error | Shows `indexing_error` value from the document row |
| Timeout / Network | "Falha ao se comunicar com o servidor." |

---

# 17. Responsive Design Specification

## 17.1 Responsive Goals

The application supports:

- Desktop
- Tablet
- Mobile devices

## 17.2 Mobile UX Priorities

Mobile layouts prioritize:

- Readable text
- Accessible upload actions
- Simplified navigation
- Stable scrolling behavior

---

# 18. Accessibility Specification

The frontend should support:

- Keyboard navigation
- Semantic HTML
- ARIA attributes
- Screen reader compatibility
- High readability contrast

---

# 19. Performance Specification

## 19.1 Frontend Performance Goals

| Metric | Target |
|---|---|
| Initial Load | < 3 seconds |
| Streaming Start | < 2 seconds after submit |
| Mobile Responsiveness | Fully responsive |
| UI Stability | Minimal layout shift |
| Polling overhead | 3-second interval only while non-terminal documents exist |

## 19.2 Optimization Strategies

- Dynamic imports for heavy components
- Lazy loading where appropriate
- Component memoization (`useMemo`, `useCallback`)
- Streaming rendering of tokens

---

# 20. Security Specification

## 20.1 Frontend Security Goals

The frontend must ensure:

- Secure token handling via Clerk (no manual JWT persistence)
- Protected routes via `middleware.ts`
- HTTPS-only communication (TLS at the edge in production)
- Upload validation (size and MIME) before sending to backend
- Sanitized markdown rendering (`react-markdown` defaults are safe; no `rehype-raw`)

## 20.2 Sensitive Data Handling

The frontend must avoid:

- Storing secrets in client code
- Persisting tokens in `localStorage`
- Logging sensitive user data

The Supabase `service_role` key MUST NEVER appear on the frontend (it lives exclusively on the backend).

---

# 21. Deployment Specification

## 21.1 Deployment Strategy

The frontend is deployed as a Docker container (Next.js standalone build). The bundled `docker-compose.yml` provides a `frontend` service that depends on `backend`.

## 21.2 Environment Variables

```text
BACKEND_URL=http://backend:8000           # destination of /api/v1/[...path] proxy
NEXT_PUBLIC_ENABLE_CLERK=false            # set to "true" to activate Clerk
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=        # Clerk public key (when enabled)
CLERK_SECRET_KEY=                         # Clerk server-side key (when enabled)
NEXT_TELEMETRY_DISABLED=1                 # disable Next.js telemetry
```

> The legacy variable `NEXT_PUBLIC_API_URL` is NOT used; calls hit the same origin and the Next.js proxy forwards them.

---

# 22. Future Evolution

Future frontend evolution may include:

- Persisted multi-session conversations
- Advanced citation exploration (click-to-open source)
- Retrieval visualization (chunk highlighting)
- In-document navigation (PDF viewer integration)
- Inline PDF preview in DocumentManager
- Advanced multimodal UX (drag-drop images into chat composer)
- Internationalization (currently pt-BR only)

---

# 23. Conclusion

The frontend architecture of the Materials Knowledge Assistant prioritizes:

- Engineering usability
- Technical readability
- Responsive interaction
- Streaming conversational UX
- Citation transparency
- Per-user document management with real-time status
- Operational simplicity (single hook, single proxy, optional auth)

The frontend complements the retrieval-grounded backend architecture, providing a clean and trustworthy interaction model.
