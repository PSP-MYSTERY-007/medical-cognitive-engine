import { z } from 'zod';
import { prisma } from '../../services/prisma.js';
import { requireAuth } from '../../middleware/auth.js';
import { callAssistant } from '../assistant/assistant.service.js';

function normalize(s) {
  return s.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
}

function scoreDiagnosis(hidden, submitted) {
  const h = normalize(hidden);
  const s = normalize(submitted);
  if (!s) return 0;
  if (s === h || s.includes(h) || h.includes(s)) return 1;
  // Partial: token overlap
  const ht = new Set(h.split(' '));
  const st = new Set(s.split(' '));
  let inter = 0;
  for (const t of st) if (ht.has(t)) inter++;
  return Math.min(0.7, inter / Math.max(1, ht.size));
}

export async function sessionsRoutes(fastify) {
  // Get session details
  fastify.get('/sessions/:sessionId', { preHandler: requireAuth }, async (request, reply) => {
    const schema = z.object({ sessionId: z.string().uuid() });
    const { sessionId } = schema.parse(request.params);
    const userId = request.user.sub;

    const session = await prisma.userCaseSession.findUnique({
      where: { id: sessionId },
      include: {
        messages: { orderBy: { createdAt: 'asc' } },
        case: { include: { disease: true } }
      }
    });

    if (!session || session.userId !== userId) {
      return reply.code(404).send({ error: 'Session not found' });
    }

    return { session };
  });

  // Chat within a session (stores messages + proxies to the existing Python assistant)
  fastify.post('/sessions/:sessionId/chat', { preHandler: requireAuth }, async (request, reply) => {
    const paramsSchema = z.object({ sessionId: z.string().uuid() });
    const bodySchema = z.object({ message: z.string().min(1), forceLocal: z.boolean().optional() });
    const { sessionId } = paramsSchema.parse(request.params);
    const { message, forceLocal } = bodySchema.parse(request.body);
    const userId = request.user.sub;

    const session = await prisma.userCaseSession.findUnique({
      where: { id: sessionId },
      include: { case: { include: { disease: true } }, messages: { orderBy: { createdAt: 'desc' }, take: 12 } }
    });
    if (!session || session.userId !== userId) {
      return reply.code(404).send({ error: 'Session not found' });
    }

    // Store user message
    await prisma.sessionMessage.create({
      data: { sessionId, role: 'user', content: message }
    });

    // Build a small history summary (v1)
    const last = [...session.messages].reverse().map(m => `${m.role}: ${m.content}`).join('\n');
    const caseHint = `Case context (do not reveal diagnosis): age ${session.case.age}, gender ${session.case.gender}, chief complaint: ${session.case.chiefComplaint}.`;
    const historySummary = `${caseHint}\n${last}`.trim();

    const assistantReply = await callAssistant({
      sessionId,
      question: message,
      historySummary,
      forceLocal: !!forceLocal
    });

    await prisma.sessionMessage.create({
      data: { sessionId, role: 'assistant', content: assistantReply }
    });

    return { reply: assistantReply };
  });

  // Submit end-of-case (basic scoring v1)
  fastify.post('/sessions/:sessionId/submit', { preHandler: requireAuth }, async (request, reply) => {
    const paramsSchema = z.object({ sessionId: z.string().uuid() });
    const bodySchema = z.object({
      finalDiagnosis: z.string().min(1),
      reasoning: z.string().optional().default(''),
      managementPlan: z.string().optional().default(''),
      durationSeconds: z.number().int().min(0).max(60 * 60).optional().default(0)
    });
    const { sessionId } = paramsSchema.parse(request.params);
    const body = bodySchema.parse(request.body);
    const userId = request.user.sub;

    const session = await prisma.userCaseSession.findUnique({
      where: { id: sessionId },
      include: { case: { include: { disease: true } } }
    });

    if (!session || session.userId !== userId) {
      return reply.code(404).send({ error: 'Session not found' });
    }

    const diagnosisScore = scoreDiagnosis(session.case.hiddenDiagnosis, body.finalDiagnosis) * 100;

    // Lightweight placeholders (you can upgrade later)
    const reasoningScore = Math.min(100, normalize(body.reasoning).length / 6);
    const managementScore = Math.min(100, normalize(body.managementPlan).length / 6);
    const historyScore = 50; // v1: assume completed

    const totalScore = 0.25 * historyScore + 0.25 * diagnosisScore + 0.25 * reasoningScore + 0.25 * managementScore;

    const updated = await prisma.userCaseSession.update({
      where: { id: sessionId },
      data: {
        historyScore,
        diagnosisScore,
        reasoningScore,
        managementScore,
        totalScore,
        durationSeconds: body.durationSeconds
      }
    });

    // Update user totals + disease progress
    const user = await prisma.user.findUnique({ where: { id: userId } });
    const newTotalSessions = (user?.totalSessions || 0) + 1;
    const newOverallScore = ((user?.overallScore || 0) * (newTotalSessions - 1) + totalScore) / newTotalSessions;

    await prisma.user.update({
      where: { id: userId },
      data: { totalSessions: newTotalSessions, overallScore: newOverallScore }
    });

    const diseaseId = session.case.diseaseId;
    const existingProg = await prisma.userDiseaseProgress.findUnique({ where: { userId_diseaseId: { userId, diseaseId } } });
    const played = (existingProg?.sessionsPlayed || 0) + 1;
    const acc = diagnosisScore / 100;
    const newAccuracy = ((existingProg?.accuracyRate || 0) * (played - 1) + acc) / played;

    await prisma.userDiseaseProgress.upsert({
      where: { userId_diseaseId: { userId, diseaseId } },
      update: { sessionsPlayed: played, accuracyRate: newAccuracy, lastPlayed: new Date() },
      create: { userId, diseaseId, sessionsPlayed: played, accuracyRate: newAccuracy, lastPlayed: new Date() }
    });

    return { session: updated, scores: { historyScore, diagnosisScore, reasoningScore, managementScore, totalScore } };
  });
}
