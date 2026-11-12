# Frontend (Next.js 16) production image — built once per commit by
# scripts/ci/build_images.sh (the PR gate and deploy.yml) and run by
# docker-compose.deploy.yml on every host (#150, #831).
#
# Multi-stage build using Next.js standalone output (next.config.mjs enables it
# when NODE_ENV=production). The image is host-agnostic: no NEXT_PUBLIC_* value is
# a build arg. The API base, the Sentry DSN and the environment tag come from the
# container's environment when a request arrives (lib/runtimeEnv.ts), so the digest
# staging tested is the one production runs.

# ── deps: install node_modules from the lockfile ────────────────────────────
# Base image digest-pinned (issue #176) for reproducible builds, matching the
# backend image. Node major MUST track CI (ci.yml builds/tests on Node 22) so
# the deployed artifact isn't an untested major (issue #277). Refresh all three
# stage pins together when bumping Node, and keep this comment honest.
# Pinned 2026-10-24 (node:22-alpine → Node 22.23.4, the CVE-2026-111497 fix); raised from Node 20 in #443
# so the runtime matches openai@7's `>=22` engines floor (Node 20 everywhere was
# blocking every openai major). This digest is Node 22.23.4, which satisfies the
# `engines` floor in package.json (^22.13.0 || >=24). `engine-strict` is not set,
# so a digest bump to an older 22.x would NOT fail npm ci — it would fail somewhere
# less obvious. Check `docker run --rm <digest> node -v` against that floor when
# bumping, and keep it on the same major CI runs (test_staging_ports guards this).
FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914 AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ── builder: produce the standalone server bundle ───────────────────────────
FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914 AS builder
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# Source maps for Sentry (#1158). Not secret, and only in the builder stage. The token is
# a secret mount below, never an ARG or ENV, so `docker history` never shows it.
ARG SENTRY_ORG=
ARG SENTRY_PROJECT=
ARG SENTRY_RELEASE=
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Build-time-only dummies, mirroring ci.yml's "Production build" env: `next
# build` imports route modules for page-data collection, and auth.ts/lib/db.ts
# need these to exist (CI=true is lib/db.ts's escape hatch for a missing
# MONGODB_URI). Scoped to this RUN only — the runner stage gets its real
# environment from docker-compose at runtime. No token (no secret, or an empty one)
# means no upload and no maps; the final `find` removes any browser map an upload left behind (only .next/static is served).
# The secret is not part of the cache key: a token change alone needs `build --no-cache`.
RUN --mount=type=secret,id=sentry_auth_token,required=false \
    SENTRY_AUTH_TOKEN="$(cat /run/secrets/sentry_auth_token 2>/dev/null || true)" \
    CI=true \
    NEXTAUTH_SECRET=build-time-dummy-not-used-at-runtime \
    NEXTAUTH_URL=http://localhost:3000 \
    GOOGLE_CLIENT_ID=dummy-client-id \
    GOOGLE_CLIENT_SECRET=dummy-client-secret \
    GITHUB_ID=dummy-client-id \
    GITHUB_SECRET=dummy-client-secret \
    npm run build \
    && find .next/static -name '*.map' -delete

# ── runner: minimal runtime image ──────────────────────────────────────────
FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914 AS runner
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
