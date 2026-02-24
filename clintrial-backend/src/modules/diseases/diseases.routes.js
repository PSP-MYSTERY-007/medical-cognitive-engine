import { z } from 'zod';
import { prisma } from '../../services/prisma.js';
import { requireRole } from '../../middleware/auth.js';

export async function diseasesRoutes(fastify) {
  fastify.get('/systems/:systemId/diseases', async (request) => {
    const schema = z.object({ systemId: z.string().uuid() });
    const { systemId } = schema.parse(request.params);
    const diseases = await prisma.disease.findMany({
      where: { systemId },
      orderBy: [ { difficultyLevel: 'asc' }, { name: 'asc' } ]
    });
    return { diseases };
  });

  fastify.post('/admin/diseases', { preHandler: requireRole(['ADMIN']) }, async (request) => {
    const schema = z.object({
      systemId: z.string().uuid(),
      name: z.string().min(2),
      difficultyLevel: z.enum(['EASY','MEDIUM','HARD']),
      metadata: z.any().optional()
    });
    const body = schema.parse(request.body);
    const disease = await prisma.disease.create({
      data: {
        systemId: body.systemId,
        name: body.name,
        difficultyLevel: body.difficultyLevel,
        metadata: body.metadata
      }
    });
    return { disease };
  });
}
