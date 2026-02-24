import { z } from 'zod';
import { prisma } from '../../services/prisma.js';
import { requireAuth, requireRole } from '../../middleware/auth.js';

export async function achievementsRoutes(fastify) {
  fastify.get('/achievements', async () => {
    const achievements = await prisma.achievement.findMany({ orderBy: { createdAt: 'desc' } });
    return { achievements };
  });

  fastify.get('/me/achievements', { preHandler: requireAuth }, async (request) => {
    const userId = request.user.sub;
    const items = await prisma.userAchievement.findMany({
      where: { userId },
      include: { achievement: true },
      orderBy: { unlockedAt: 'desc' }
    });
    return { achievements: items };
  });

  fastify.post('/admin/achievements', { preHandler: requireRole(['ADMIN']) }, async (request) => {
    const schema = z.object({
      title: z.string().min(2),
      description: z.string().min(2),
      badgeIcon: z.string().min(1),
      conditionLogic: z.any()
    });
    const body = schema.parse(request.body);
    const achievement = await prisma.achievement.create({ data: body });
    return { achievement };
  });
}
