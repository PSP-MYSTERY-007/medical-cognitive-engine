import { PrismaClient, Difficulty, Role } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function ensureAdmin() {
  const email = 'admin@local.test';
  const passwordHash = await bcrypt.hash('admin1234', 12);
  await prisma.user.upsert({
    where: { email },
    update: {},
    create: {
      fullName: 'Local Admin',
      email,
      passwordHash,
      role: Role.ADMIN
    }
  });
  return email;
}

async function main() {
  const ukm = await prisma.university.upsert({
    where: { uniqueCode: 'UKM' },
    update: {},
    create: { name: 'Universiti Kebangsaan Malaysia', country: 'Malaysia', uniqueCode: 'UKM' }
  });

  const adminEmail = await ensureAdmin();

  // Systems
  const cardiology = await prisma.system.upsert({
    where: { name: 'Cardiology' },
    update: {},
    create: { name: 'Cardiology' }
  });
  const respiratory = await prisma.system.upsert({
    where: { name: 'Respiratory' },
    update: {},
    create: { name: 'Respiratory' }
  });
  const endocrine = await prisma.system.upsert({
    where: { name: 'Endocrine' },
    update: {},
    create: { name: 'Endocrine' }
  });

  // Diseases + Cases (small starter set)
  const diseases = [
    { system: cardiology, name: 'Heart Failure', level: Difficulty.MEDIUM },
    { system: cardiology, name: 'Acute Coronary Syndrome', level: Difficulty.HARD },
    { system: respiratory, name: 'Asthma Exacerbation', level: Difficulty.MEDIUM },
    { system: respiratory, name: 'Community Acquired Pneumonia', level: Difficulty.MEDIUM },
    { system: endocrine, name: 'Type 2 Diabetes', level: Difficulty.EASY },
    { system: endocrine, name: 'Diabetic Ketoacidosis', level: Difficulty.HARD }
  ];

  for (const d of diseases) {
    const disease = await prisma.disease.upsert({
      where: { systemId_name: { systemId: d.system.id, name: d.name } },
      update: { difficultyLevel: d.level },
      create: {
        systemId: d.system.id,
        name: d.name,
        difficultyLevel: d.level,
        metadata: { tags: ['seed'] }
      }
    });

    // Ensure at least one case per disease
    const existing = await prisma.case.count({ where: { diseaseId: disease.id } });
    if (existing === 0) {
      await prisma.case.create({
        data: {
          diseaseId: disease.id,
          age: 58,
          gender: 'Male',
          chiefComplaint: `Seed case for ${d.name}`,
          hiddenDiagnosis: d.name,
          difficulty: d.level,
          structuredCaseData: {
            chiefComplaint: `Seed case for ${d.name}`,
            history: { onset: '2 days', symptoms: ['shortness of breath'] },
            exam: { vitals: { hr: 110, bp: '140/90', rr: 22 }, findings: [] },
            investigations: { ecg: '', labs: {} },
            managementKeyPoints: []
          }
        }
      });
    }
  }

  console.log('Seed complete. Admin login:', adminEmail, 'password: admin1234');
  console.log('University:', ukm.name, '(' + ukm.uniqueCode + ')');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
