# syntax=docker/dockerfile:1.6

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — deps: install node_modules once, reuse in the builder stage.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app

# libc6-compat is required for some Next.js native bindings on Alpine.
RUN apk add --no-cache libc6-compat

COPY package.json package-lock.json ./
RUN npm ci


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — builder: run `next build` and produce .next/standalone.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* vars are inlined into the client JS bundle at build time.
# They must be present during `npm run build`, not just at container start.
# Pass them via docker-compose `build.args` or `--build-arg` on the CLI.
ARG NEXT_PUBLIC_APP_NAME="Multi-Agent Opinion Simulator"
ENV NEXT_PUBLIC_APP_NAME=$NEXT_PUBLIC_APP_NAME
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — runner: minimal image containing only what the standalone server
# needs at runtime. No node_modules, no build cache, no source files.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Run as a non-root user. The official Next.js Docker example uses uid 1001.
RUN addgroup --system --gid 1001 nodejs \
    && adduser  --system --uid 1001 nextjs

# `output: "standalone"` copies some assets into .next/standalone/ but not
# all of them. These three COPY commands reconstruct the layout the
# standalone server.js expects:
#   /app/server.js           ← standalone entrypoint
#   /app/.next/static/       ← client JS/CSS bundles
#   /app/public/             ← favicon, SVGs, etc.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

# The correct entrypoint for `output: "standalone"`. `next start` would
# refuse to run — the standalone build does not ship the full node_modules
# tree that next start expects.
CMD ["node", "server.js"]