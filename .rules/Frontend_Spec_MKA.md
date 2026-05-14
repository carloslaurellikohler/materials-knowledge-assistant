# Frontend Specification (FES)
## Materials Knowledge Assistant (MKA)

Version: 1.0  
Status: Draft  
Author: Carlos Eduardo  
Date: May 2026

---

# 1. Purpose

This document defines the frontend specification for the Materials Knowledge Assistant (MKA).

The frontend is responsible for delivering a modern, responsive, engineering-oriented user experience focused on:

- Conversational AI interaction
- Citation visualization
- Technical readability
- File upload workflows
- Multimodal interaction
- Streaming AI responses

---

# 2. Frontend Technology Stack

| Layer | Technology |
|---|---|
| Framework | Next.js |
| Language | TypeScript |
| Styling | TailwindCSS |
| UI Components | shadcn/ui |
| Authentication | Clerk |
| State Management | React Context + Hooks |
| API Communication | REST + Streaming |
| Markdown Rendering | react-markdown |
| Hosting | Vercel or Railway |

---

# 3. Frontend Architectural Principles

The frontend implementation should prioritize:

- Technical readability
- Minimal cognitive load
- Responsive layouts
- Streaming-first UX
- Modular UI components
- Accessibility
- Fast rendering
- Engineering-oriented interaction

---

# 4. Project Structure

```text
frontend/
│
├── app/
│   ├── chat/
│   ├── upload/
│   ├── auth/
│   └── layout.tsx
│
├── components/
│   ├── chat/
│   ├── citations/
│   ├── upload/
│   ├── markdown/
│   ├── layout/
│   └── ui/
│
├── hooks/
├── services/
├── lib/
├── types/
├── styles/
├── public/
└── middleware.ts
```

---

# 5. UI Architecture

## 5.1 Core UI Modules

| Module | Responsibility |
|---|---|
| Auth Module | Authentication flow |
| Chat Module | Conversational interface |
| Upload Module | File upload workflows |
| Citation Renderer | Citation display |
| Markdown Renderer | AI response formatting |
| Streaming Handler | Incremental token rendering |
| Session Manager | Local session state |

---

# 6. Authentication Flow

## 6.1 Authentication Strategy

Authentication uses:

- Google OAuth
- Clerk authentication
- JWT-based session handling

---

## 6.2 Frontend Responsibilities

The frontend must:

- Redirect unauthenticated users
- Manage Clerk sessions
- Attach auth tokens to requests
- Protect private routes

---

# 7. Chat Interface Specification

## 7.1 Chat Goals

The chat experience should provide:

- Real-time interaction
- Streaming AI responses
- Markdown rendering
- Citation rendering
- Mobile responsiveness

---

## 7.2 Chat Layout

Suggested layout:

```text
+-----------------------------------+
| Header                            |
+-----------------------------------+
| Sidebar (future support optional) |
+-----------------------------------+
| Conversation Window               |
|                                   |
| User Messages                     |
| AI Responses                      |
| Citations                         |
|                                   |
+-----------------------------------+
| Input + Upload Actions            |
+-----------------------------------+
```

---

## 7.3 Message Types

| Type | Description |
|---|---|
| User Message | User-generated prompt |
| AI Response | Generated response |
| Citation Block | Retrieved source references |
| Upload Status | File processing status |
| Error Message | Structured error rendering |

---

# 8. Streaming UX Specification

## 8.1 Streaming Goals

The interface should:

- Display tokens incrementally
- Reduce perceived latency
- Avoid layout shifting
- Preserve scroll behavior

---

## 8.2 Streaming Strategy

Streaming should use:

- Server-Sent Events (SSE)
- Incremental rendering
- Optimistic UI updates

---

# 9. File Upload Specification

## 9.1 Supported Uploads

| Type | Purpose |
|---|---|
| PDF | Knowledge ingestion |
| Image | Visual analysis |
| Audio | Speech transcription |

---

## 9.2 Upload UX Requirements

The upload experience should include:

- Drag-and-drop support
- Upload progress indicators
- Validation messages
- Processing state indicators

---

## 9.3 File Validation

| Rule | Requirement |
|---|---|
| PDF Max Size | 100MB |
| Image Formats | PNG, JPG, WEBP |
| Audio Formats | MP3, WAV, M4A |

---

# 10. Citation Rendering Specification

## 10.1 Citation Goals

The citation layer should provide:

- Traceability
- Readability
- Source transparency
- Engineering confidence

---

## 10.2 Citation UI Elements

Each citation should display:

- Source document
- Section title
- Page number
- Excerpt preview

---

## 10.3 Citation Example

```text
Source: Materials Science and Engineering
Section: Galvanic Corrosion
Page: 248
```

---

# 11. Markdown Rendering Specification

## 11.1 Supported Markdown Features

| Feature | Support |
|---|---|
| Headings | Yes |
| Lists | Yes |
| Tables | Yes |
| Code Blocks | Yes |
| Inline Code | Yes |
| Blockquotes | Yes |

---

## 11.2 Rendering Goals

Markdown rendering should prioritize:

- Technical readability
- Clean typography
- Proper spacing
- Mobile responsiveness

---

# 12. Responsive Design Specification

## 12.1 Responsive Goals

The application must support:

- Desktop
- Tablet
- Mobile devices

---

## 12.2 Mobile UX Priorities

Mobile layouts should prioritize:

- Readable text
- Accessible upload actions
- Simplified navigation
- Stable scrolling behavior

---

# 13. State Management Specification

## 13.1 State Strategy

The frontend should use:

- React Context
- React Hooks
- Local component state

Avoid unnecessary global state complexity in V1.

---

## 13.2 State Domains

| State Domain | Responsibility |
|---|---|
| Auth State | User authentication |
| Chat State | Active conversation |
| Upload State | File uploads |
| Streaming State | AI streaming status |
| Error State | UI error handling |

---

# 14. API Communication Specification

## 14.1 Communication Strategy

The frontend communicates with the backend using:

- REST APIs
- Streaming responses
- Multipart uploads

---

## 14.2 Request Headers

Protected requests should include:

```text
Authorization: Bearer <JWT>
```

---

# 15. Error Handling UX

## 15.1 UX Goals

The UI should provide:

- Human-readable errors
- Retry mechanisms
- Graceful fallback states
- Stable rendering during failures

---

## 15.2 Example Error Messages

| Error | UI Message |
|---|---|
| Upload Failure | "Unable to upload file." |
| Retrieval Failure | "No relevant literature found." |
| Timeout | "The request took too long to complete." |

---

# 16. Accessibility Specification

## 16.1 Accessibility Goals

The frontend should support:

- Keyboard navigation
- Semantic HTML
- ARIA attributes
- Screen reader compatibility
- High readability contrast

---

# 17. Performance Specification

## 17.1 Frontend Performance Goals

| Metric | Target |
|---|---|
| Initial Load | < 3 seconds |
| Streaming Start | < 2 seconds |
| Mobile Responsiveness | Fully responsive |
| UI Stability | Minimal layout shift |

---

## 17.2 Optimization Strategies

Recommended optimizations:

- Dynamic imports
- Lazy loading
- Component memoization
- Optimized image rendering
- Streaming rendering

---

# 18. Security Specification

## 18.1 Frontend Security Goals

The frontend must ensure:

- Secure token handling
- Protected routes
- HTTPS-only communication
- Upload validation
- Sanitized markdown rendering

---

## 18.2 Sensitive Data Handling

The frontend must avoid:

- Storing secrets
- Persisting tokens insecurely
- Logging sensitive user data

---

# 19. Deployment Specification

## 19.1 Deployment Strategy

The frontend should be deployed using:

- Vercel
- Railway

---

## 19.2 Environment Variables

Required frontend variables:

```text
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
NEXT_PUBLIC_API_URL=
```

---

# 20. Future Evolution

Future frontend evolution may include:

- Multi-session conversations
- Advanced citation exploration
- Retrieval visualization
- Document navigation
- Collaborative engineering workflows
- Advanced multimodal UX

---

# 21. Conclusion

The frontend architecture of the Materials Knowledge Assistant prioritizes:

- Engineering usability
- Technical readability
- Responsive interaction
- Streaming conversational UX
- Citation transparency
- Operational simplicity

The frontend should provide a clean and trustworthy interaction model that complements the retrieval-grounded AI architecture of the platform.
