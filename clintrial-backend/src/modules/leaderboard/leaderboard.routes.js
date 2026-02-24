import { z } from 'zod';
import { prisma } from '../../services/prisma.js';
import { getRedis } from '../../services/redis.js';

export async function leaderboardRoutes(fastify) {
  fastify.get('/leaderboard', async (request) => {
    const schema = z.object({
      type: z.enum(['global','university']).optional().default('global'),
      universityId: z.string().uuid().optional(),
      minSessions: z.string().optional(),
      limit: z.string().optional()
    });
    const q = schema.parse(request.query);
    const minSessions = Math.max(parseInt(q.minSessions || '3', 10), 0);
    const limit = Math.min(parseInt(q.limit || '20', 10), 100);

    const redis = getRedis();
    const cacheKey = `leaderboard:${q.type}:${q.universityId || 'all'}:${minSessions}:${limit}`;
    if (redis) {
      const cached = await redis.get(cacheKey);
      if (cached) return JSON.parse(cached);
    }

    const where = {
      totalSessions: { gte: minSessions },
      ...(q.type === 'university' && q.universityId ? { universityId: q.universityId } : {})
    };

    const users = await prisma.user.findMany({
      where,
      orderBy: [{ overallScore: 'desc' }, { totalSessions: 'desc' }],
      take: limit,
      select: { id: true, fullName: true, overallScore: true, totalSessions: true, universityId: true, rankLevel: true }
    });

    const result = { type: q.type, minSessions, limit, users };

    if (redis) {
      await redis.set(cacheKey, JSON.stringify(result), 'EX', 30);
    }

    return result;
  });
}
