import { prisma } from '../../services/prisma.js';
import { requireAuth } from '../../middleware/auth.js';

export async function analyticsRoutes(fastify) {
  fastify.get('/analytics/summary', { preHandler: requireAuth }, async (request) => {
    const userId = request.user.sub;

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { overallScore: true, totalSessions: true, streakDays: true, rankLevel: true }
    });

    const diseaseProgress = await prisma.userDiseaseProgress.findMany({
      where: { userId },
      include: { disease: { include: { system: true } } }
    });

    // Aggregate by system
    const bySystem = new Map();
    for (const p of diseaseProgress) {
      const sys = p.disease.system.name;
      const entry = bySystem.get(sys) || { system: sys, diseases: 0, sessions: 0, avgAccuracy: 0 };
      entry.diseases += 1;
      entry.sessions += p.sessionsPlayed;
      entry.avgAccuracy += p.accuracyRate;
      bySystem.set(sys, entry);
    }
    const systems = [...bySystem.values()].map(x => ({
      system: x.system,
      diseasesTracked: x.diseases,
      sessions: x.sessions,
      avgAccuracy: x.diseases ? x.avgAccuracy / x.diseases : 0
    })).sort((a,b) => a.system.localeCompare(b.system));

    // Weakest disease
    const weakestDisease = diseaseProgress.length
      ? diseaseProgress.reduce((min, p) => (p.accuracyRate < min.accuracyRate ? p : min), diseaseProgress[0])
      : null;

    return {
      user,
      systems,
      weakest: weakestDisease ? {
        disease: weakestDisease.disease.name,
        system: weakestDisease.disease.system.name,
        accuracyRate: weakestDisease.accuracyRate,
        sessionsPlayed: weakestDisease.sessionsPlayed
      } : null
    };
  });
}
