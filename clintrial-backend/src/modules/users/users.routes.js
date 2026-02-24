import { z } from 'zod';
import { prisma } from '../../services/prisma.js';
import { requireAuth, requireRole } from '../../middleware/auth.js';

export async function usersRoutes(fastify) {
  fastify.get('/me', { preHandler: requireAuth }, async (request) => {
    const userId = request.user.sub;
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        fullName: true,
        email: true,
        role: true,
        universityId: true,
        totalSessions: true,
        overallScore: true,
        streakDays: true,
        rankLevel: true,
        createdAt: true
      }
    });
    return { user };
  });

  fastify.patch('/me', { preHandler: requireAuth }, async (request) => {
    const schema = z.object({ fullName: z.string().min(2).optional(), universityId: z.string().uuid().optional() });
    const body = schema.parse(request.body);
    const userId = request.user.sub;
    const user = await prisma.user.update({
      where: { id: userId },
      data: body,
      select: { id: true, fullName: true, email: true, role: true, universityId: true }
    });
    return { user };
  });

  // Admin list users
  fastify.get('/admin/users', { preHandler: requireRole(['ADMIN']) }, async (request) => {
    const take = Math.min(parseInt(request.query.take || '50', 10), 200);
    const skip = Math.max(parseInt(request.query.skip || '0', 10), 0);
    const users = await prisma.user.findMany({
      take,
      skip,
      orderBy: { createdAt: 'desc' },
      select: { id: true, fullName: true, email: true, role: true, universityId: true, totalSessions: true, overallScore: true, createdAt: true }
    });
    return { users };
  });
}
