import { z } from 'zod';
import { prisma } from '../../services/prisma.js';
import { requireRole } from '../../middleware/auth.js';

export async function universitiesRoutes(fastify) {
  fastify.get('/universities', async () => {
    const items = await prisma.university.findMany({ orderBy: { name: 'asc' } });
    return { universities: items };
  });

  fastify.post('/admin/universities', { preHandler: requireRole(['ADMIN']) }, async (request) => {
    const schema = z.object({
      name: z.string().min(2),
      country: z.string().min(2),
      uniqueCode: z.string().min(2).max(16)
    });
    const body = schema.parse(request.body);
    const uni = await prisma.university.create({ data: body });
    return { university: uni };
  });
}
