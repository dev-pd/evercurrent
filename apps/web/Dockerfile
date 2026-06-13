FROM node:25-alpine AS builder

RUN npm install -g pnpm@latest

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,id=pnpm-store,target=/root/.local/share/pnpm/store \
    pnpm config set store-dir /root/.local/share/pnpm/store \
 && pnpm install --frozen-lockfile

COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:25-alpine AS dev

RUN apk add --no-cache bash \
 && npm install -g pnpm@latest

WORKDIR /app

COPY --from=builder /app/node_modules /app/node_modules
COPY --from=builder /app /app

ENV NODE_ENV=development \
    NEXT_TELEMETRY_DISABLED=1

CMD ["pnpm", "dev"]

FROM node:25-alpine AS runtime

RUN addgroup -g 1001 -S nodejs \
 && adduser -u 1001 -S nextjs -G nodejs

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=5 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:3000 || exit 1

CMD ["node", "server.js"]
