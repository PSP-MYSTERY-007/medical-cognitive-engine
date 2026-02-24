import { z } from 'zod';
import { prisma } from '../../services/prisma.js';
import { requireRole } from '../../middleware/auth.js';

export async function systemsRoutes(fastify) {
  fastify.get('/systems', async () => {
    const systems = await prisma.system.findMany({ orderBy: { name: 'asc' } });
    return { systems };
  });

  fastify.post('/admin/systems', { preHandler: requireRole(['ADMIN']) }, async (request) => {
    const schema = z.object({ name: z.string().min(2) });
    const body = schema.parse(request.body);
    const system = await prisma.system.create({ data: body });
    return { system };
  });
}
