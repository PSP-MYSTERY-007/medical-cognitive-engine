import { z } from 'zod';
import { requireAuth } from '../../middleware/auth.js';
import { callAssistant } from './assistant.service.js';
import { v4 as uuidv4 } from 'uuid';

export async function assistantRoutes(fastify) {
  fastify.post('/assistant/query', { preHandler: requireAuth }, async (request, reply) => {
    const schema = z.object({
      sessionId: z.string().uuid().optional(),
      question: z.string().min(1),
      historySummary: z.string().optional(),
      forceLocal: z.boolean().optional()
    });
    const body = schema.parse(request.body);

    const sessionId = body.sessionId || uuidv4();
    const answer = await callAssistant({
      sessionId,
      question: body.question,
      historySummary: body.historySummary || '',
      forceLocal: !!body.forceLocal
    });

    return reply.send({ sessionId, answer });
  });
}
