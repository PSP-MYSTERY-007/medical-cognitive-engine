import { z } from 'zod';
import { prisma } from '../../services/prisma.js';
import { requireAuth, requireRole } from '../../middleware/auth.js';

function weightedPick(items) {
  const total = items.reduce((s, x) => s + x.weight, 0);
  let r = Math.random() * total;
  for (const x of items) {
    r -= x.weight;
    if (r <= 0) return x.item;
  }
  return items[items.length - 1].item;
}

export async function casesRoutes(fastify) {
  const listMedicalCasesHandler = async (request) => {
    const querySchema = z.object({
      difficulty: z.string().optional()
    });
    const { difficulty } = querySchema.parse(request.query ?? {});

    const normalizedDifficulty = (difficulty ?? '').trim().toLowerCase();
    const where = normalizedDifficulty
      ? { difficulty: { equals: normalizedDifficulty, mode: 'insensitive' } }
      : {};
    const medicalCases = await prisma.medicalCase.findMany({
      where,
      orderBy: { createdAt: 'desc' }
    });

    return { medicalCases };
  };

  fastify.get('/medical-cases', listMedicalCasesHandler);
  fastify.get('/cases/medical-cases', listMedicalCasesHandler);

  // User-facing: select a case by system + difficulty (weighted by weak areas)
  fastify.post('/cases/select', { preHandler: requireAuth }, async (request, reply) => {
    const bodySchema = z.object({
      systemId: z.string().uuid(),
      difficulty: z.enum(['EASY','MEDIUM','HARD'])
    });
    const { systemId, difficulty } = bodySchema.parse(request.body);
    const userId = request.user.sub;

    // Avoid repeating cases from last N sessions
    const recentSessions = await prisma.userCaseSession.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      take: 12,
      select: { caseId: true }
    });
    const recentCaseIds = new Set(recentSessions.map(s => s.caseId));

    const diseases = await prisma.disease.findMany({
      where: { systemId, difficultyLevel: difficulty },
      include: { cases: true }
    });

    if (diseases.length === 0) {
      return reply.code(404).send({ error: 'No diseases found for this system+difficulty' });
    }

    // Build weights from user progress (lower accuracy = higher weight)
    const progress = await prisma.userDiseaseProgress.findMany({
      where: { userId, disease: { systemId } },
      select: { diseaseId: true, accuracyRate: true }
    });
    const progressMap = new Map(progress.map(p => [p.diseaseId, p.accuracyRate]));

    const weightedDiseases = diseases.map(d => {
      const acc = progressMap.get(d.id);
      const weakness = acc === undefined ? 0.5 : Math.max(0, 1 - acc);
      // Base weight so new/unknown diseases still show up
      return { item: d, weight: 0.5 + weakness };
    });

    // Try up to a few picks to avoid recent cases
    let chosen = null;
    for (let i = 0; i < 5; i++) {
      const disease = weightedPick(weightedDiseases);
      const availableCases = disease.cases.filter(c => !recentCaseIds.has(c.id));
      const pool = availableCases.length ? availableCases : disease.cases;
      if (pool.length === 0) continue;
      chosen = pool[Math.floor(Math.random() * pool.length)];
      break;
    }

    if (!chosen) {
      return reply.code(404).send({ error: 'No cases available for selection' });
    }

    // Start a session record immediately (so you can track duration + chat)
    const session = await prisma.userCaseSession.create({
      data: { userId, caseId: chosen.id }
    });

    return {
      session,
      case: {
        id: chosen.id,
        diseaseId: chosen.diseaseId,
        age: chosen.age,
        gender: chosen.gender,
        chiefComplaint: chosen.chiefComplaint,
        difficulty: chosen.difficulty,
        structuredCaseData: chosen.structuredCaseData
      }
    };
  });

  // Admin: create case
  fastify.post('/admin/cases', { preHandler: requireRole(['ADMIN']) }, async (request) => {
    const schema = z.object({
      diseaseId: z.string().uuid(),
      age: z.number().int().min(0).max(120),
      gender: z.string().min(1),
      chiefComplaint: z.string().min(1),
      hiddenDiagnosis: z.string().min(1),
      difficulty: z.enum(['EASY','MEDIUM','HARD']),
      structuredCaseData: z.any()
    });
    const body = schema.parse(request.body);

    const c = await prisma.case.create({
      data: {
        diseaseId: body.diseaseId,
        age: body.age,
        gender: body.gender,
        chiefComplaint: body.chiefComplaint,
        hiddenDiagnosis: body.hiddenDiagnosis,
        difficulty: body.difficulty,
        structuredCaseData: body.structuredCaseData
      }
    });

    return { case: c };
  });

  // Admin: list cases by disease
  fastify.get('/admin/diseases/:diseaseId/cases', { preHandler: requireRole(['ADMIN']) }, async (request) => {
    const schema = z.object({ diseaseId: z.string().uuid() });
    const { diseaseId } = schema.parse(request.params);
    const cases = await prisma.case.findMany({ where: { diseaseId }, orderBy: { createdAt: 'desc' } });
    return { cases };
  });
}
