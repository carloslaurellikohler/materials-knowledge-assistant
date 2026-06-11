FROM node:20-slim

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY package*.json ./
RUN npm ci

COPY . .

# Variáveis públicas do Next.js: NEXT_PUBLIC_* são "assadas" (inlined) durante o
# `next build`, não lidas em runtime. Por isso precisam estar presentes AQUI,
# como build args, senão o Clerk fica desligado na imagem de produção.
ARG NEXT_PUBLIC_ENABLE_CLERK=false
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
ENV NEXT_PUBLIC_ENABLE_CLERK=${NEXT_PUBLIC_ENABLE_CLERK}
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}

RUN npm run build

EXPOSE 3000

CMD ["sh", "-c", "npm run start -- --hostname 0.0.0.0 --port ${PORT:-3000}"]
