# Frontend (Next.js 16) production image — built by docker-compose.staging.yml
# and deployed by .github/workflows/deploy.yml (issue #150).
#
# Multi-stage build using Next.js standalone output (next.config.mjs enables it
# when NODE_ENV=production). NEXT_PUBLIC_* values are inlined at build time, so
# NEXT_PUBLIC_API_URL must be supplied as a build arg by the compose file.

# ── deps: install node_modules from the lockfile ────────────────────────────
# Base image digest-pinned (issue #176) for reproducible builds, matching the
# backend image. Node major MUST track CI (ci.yml builds/tests on Node 22) so
# the deployed artifact isn't an untested major (issue #277). Refresh all three
# stage pins together when bumping Node, and keep this comment honest.
# Pinned 2026-09-13 (node:22-alpine → Node 22.23.2); raised from Node 20 in #443
# so the runtime matches openai@7's `>=22` engines floor (Node 20 everywhere was
# blocking every openai major). This digest is Node 22.23.2, which satisfies the
# `engines` floor in package.json (^22.13.0 || >=24). `engine-strict` is not set,
# so a digest bump to an older 22.x would NOT fail npm ci — it would fail somewhere
# less obvious. Check `docker run --rm <digest> node -v` against that floor when
# bumping, and keep it on the same major CI runs (test_staging_ports guards this).
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ── builder: produce the standalone server bundle ───────────────────────────
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Build-time-only dummies, mirroring ci.yml's "Production build" env: `next
# build` imports route modules for page-data collection, and auth.ts/lib/db.ts
# need these to exist (CI=true is lib/db.ts's escape hatch for a missing
# MONGODB_URI). Scoped to this RUN only — the runner stage gets its real
# environment from docker-compose at runtime.
RUN CI=true \
    NEXTAUTH_SECRET=build-time-dummy-not-used-at-runtime \
    NEXTAUTH_URL=http://localhost:3000 \
    GOOGLE_CLIENT_ID=dummy-client-id \
    GOOGLE_CLIENT_SECRET=dummy-client-secret \
    GITHUB_ID=dummy-client-id \
    GITHUB_SECRET=dummy-client-secret \
    npm run build

# ── runner: minimal runtime image ──────────────────────────────────────────
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# curl backs the compose healthcheck; run as a non-root user.
RUN apk add --no-cache curl \
    && addgroup -g 1001 -S nodejs \
    && adduser -S nextjs -u 1001

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:3000 || exit 1

CMD ["node", "server.js"]
