---
name: wiki_stack
description: Compiled wiki — tech stack, architecture, deployment config, third-party services
type: project
---
# Tech Stack — Compiled Wiki

## Frontend
- Next.js 14 (App Router)
- Tailwind CSS + shadcn/ui
- Deployed on Vercel (auto-deploy from main)

## Backend
- Node.js + Fastify
- PostgreSQL 16 (Supabase)
- Redis for sessions + rate limiting
- Deployed on Railway

## Auth
- Clerk (switched from NextAuth in March)
- JWT tokens, 15min expiry
- Refresh tokens in httpOnly cookies

## API
- REST for public endpoints
- tRPC for internal frontend ↔ backend
- Rate limit: 100 req/min per user

## Monitoring
- Sentry for errors
- Posthog for analytics
- Uptime: betterstack.com

## Environments
| Env | URL | Branch |
|-----|-----|--------|
| Production | app.example.com | main |
| Staging | staging.example.com | develop |
| Local | localhost:3000 | any |
