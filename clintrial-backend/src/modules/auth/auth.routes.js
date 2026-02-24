import { z } from 'zod';
import {
  register,
  login,
  issueTokens,
  rotateRefreshToken,
  logout,
  requestPasswordReset,
  resetPassword
} from './auth.service.js';

export async function authRoutes(fastify) {
  fastify.post('/auth/register', async (request, reply) => {
    const schema = z.object({
      fullName: z.string().min(2),
      email: z.string().email(),
      password: z.string().min(8),
      universityCode: z.string().optional(),
      role: z.enum(['STUDENT','DOCTOR','ADMIN','UNIVERSITY_ADMIN']).optional()
    });
    const body = schema.parse(request.body);

    const user = await register(body);
    const tokens = await issueTokens(fastify, user.id, user.role);
    return reply.send({ user, tokens });
  });

  fastify.post('/auth/login', async (request, reply) => {
    const schema = z.object({ email: z.string().email(), password: z.string().min(1) });
    const body = schema.parse(request.body);
    const result = await login(fastify, body);
    return reply.send(result);
  });

  fastify.post('/auth/refresh', async (request, reply) => {
    const schema = z.object({ refreshToken: z.string().min(1) });
    const body = schema.parse(request.body);
    const result = await rotateRefreshToken(fastify, body);
    return reply.send(result);
  });

  fastify.post('/auth/logout', async (request, reply) => {
    const schema = z.object({ refreshToken: z.string().min(1) });
    const body = schema.parse(request.body);
    await logout(body);
    return reply.send({ ok: true });
  });

  fastify.post('/auth/password/forgot', async (request, reply) => {
    const schema = z.object({ email: z.string().email() });
    const body = schema.parse(request.body);
    const result = await requestPasswordReset(body);
    return reply.send(result);
  });

  fastify.post('/auth/password/reset', async (request, reply) => {
    const schema = z.object({ token: z.string().min(1), newPassword: z.string().min(8) });
    const body = schema.parse(request.body);
    const result = await resetPassword(body);
    return reply.send(result);
  });
}
