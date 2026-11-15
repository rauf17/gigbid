# Web UI Dockerfile (Next.js 14 App Router)
FROM node:20-bookworm-slim AS builder

WORKDIR /app

COPY apps/web/package*.json ./
RUN npm ci

COPY apps/web/ ./
RUN npm run build

FROM node:20-bookworm-slim AS runner

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000

COPY --from=builder /app ./

EXPOSE 3000

CMD ["npm", "start", "--", "-p", "3000"]
