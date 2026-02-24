import Fastify from 'fastify';
import cors from '@fastify/cors';
import jwt from '@fastify/jwt';
import sensible from '@fastify/sensible';
import rateLimit from '@fastify/rate-limit';
import { ZodError } from 'zod';
import { env } from './utils/env.js';
import { prisma } from './services/prisma.js';

import { authRoutes } from './modules/auth/auth.routes.js';
import { usersRoutes } from './modules/users/users.routes.js';
import { universitiesRoutes } from './modules/universities/universities.routes.js';
import { systemsRoutes } from './modules/systems/systems.routes.js';
import { diseasesRoutes } from './modules/diseases/diseases.routes.js';
import { casesRoutes } from './modules/cases/cases.routes.js';
import { sessionsRoutes } from './modules/sessions/sessions.routes.js';
import { analyticsRoutes } from './modules/analytics/analytics.routes.js';
import { leaderboardRoutes } from './modules/leaderboard/leaderboard.routes.js';
import { achievementsRoutes } from './modules/achievements/achievements.routes.js';
import { assistantRoutes } from './modules/assistant/assistant.routes.js';

const app = Fastify({ logger: true });

await app.register(cors, { origin: true, credentials: true });
await app.register(sensible);
await app.register(rateLimit, { max: 200, timeWindow: '1 minute' });

await app.register(jwt, {
  secret: env.JWT_ACCESS_SECRET,
  sign: { expiresIn: env.ACCESS_TOKEN_TTL_SECONDS }
});

// Provide a separate signer for refresh if needed
app.decorate('signRefresh', (payload, opts) => app.jwt.sign(payload, { ...opts, secret: env.JWT_REFRESH_SECRET }));

app.setErrorHandler((err, request, reply) => {
  if (err instanceof ZodError) {
    return reply.code(400).send({ error: 'ValidationError', details: err.errors });
  }
  const status = err.statusCode || 500;
  request.log.error(err);
  reply.code(status).send({ error: err.message || 'ServerError' });
});

app.get('/health', async () => {
  // quick db check
  await prisma.$queryRaw`SELECT 1`;
  return { ok: true };
});

// Register routes
await app.register(authRoutes);
await app.register(usersRoutes);
await app.register(universitiesRoutes);
await app.register(systemsRoutes);
await app.register(diseasesRoutes);
await app.register(casesRoutes);
await app.register(sessionsRoutes);
await app.register(analyticsRoutes);
await app.register(leaderboardRoutes);
await app.register(achievementsRoutes);
await app.register(assistantRoutes);

app.listen({ port: env.PORT, host: env.HOST }).then(() => {
  app.log.info(`ClinTrial backend listening on http://${env.HOST}:${env.PORT}`);
}).catch((e) => {
  app.log.error(e);
  process.exit(1);
});
