import { PrismaClient, Difficulty, Role } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

// -------------------------
// Cardiology medical cases
// -------------------------
const cardiologyMedicalCases = [
  {
    age: 62,
    gender: 'Female',
    chiefComplaint: 'Shortness of breath and palpitations',
    hiddenDiagnosis: 'Atrial Fibrillation (AFib)',
    difficulty: 'Medium',
    structuredData: {
      history: {
        onset: '4 hours ago while sitting and watching TV.',
        rhythmDescription: "Heart feels like it is 'fluttering' or 'jumping around' with no regular beat.",
        associatedSymptoms: ['Lightheadedness', 'General fatigue', 'Mild shortness of breath'],
        redFlags: {
          chestPain: 'None',
          syncope: 'None (just dizzy)',
          focalWeakness: 'None (No numbness or trouble speaking)'
        },
        priorHistory: ['Hypertension (dx 5 years ago)', 'Obstructive Sleep Apnea (uses CPAP occasionally)'],
        familyHistory: 'Father had a stroke at 68; Mother has high blood pressure.',
        socialHistory: {
          smoking: 'Never smoked.',
          alcohol: '1-2 glasses of wine on weekends.',
          caffeine: '2 cups of tea daily.',
          livingSituation: 'Lives with husband in a single-story house.'
        },
        medications: ['Amlodipine 5mg once daily', 'Multivitamins']
      },
      physicalExam: {
        vitals: {
          bp: '132/84',
          hr: '142 (Irregularly irregular)',
          rr: 19,
          spo2: '96% on room air',
          temp: '36.7°C'
        },
        findings: {
          general: 'Alert and oriented, but looks slightly pale and anxious.',
          cardiovascular: 'Apex beat is irregularly irregular. Notable pulse deficit (radial pulse is slower than apical heart rate). JVP is normal.',
          respiratory: 'Lungs are clear; no crackles or wheezing.',
          peripheral: 'No ankle swelling (edema). Calves are soft and non-tender (no DVT).'
        }
      },
      investigations: {
        ecg: 'Narrow complex tachycardia, absent P-waves, and irregularly irregular R-R intervals.',
        labs: {
          troponin: 'Negative (<0.01 ng/mL)',
          tsh: 'Normal (1.2 mIU/L)',
          electrolytes: 'Potassium: 4.0, Magnesium: 1.9 (All within normal range)',
          fullBloodCount: 'Normal hemoglobin and white cell count.'
        }
      },
      managementKeyPoints: [
        'Confirm Irregularly Irregular pulse on exam',
        'Correctly interpret ECG as Atrial Fibrillation',
        'Assess stroke risk using CHA2DS2-VASc (Score: 3 - Female, HTN, Age 65 approach)',
        'Propose Rate Control (e.g., Beta-blocker like Metoprolol or Bisoprolol)',
        'Initiate Anticoagulation (e.g., Apixaban or Warfarin) for stroke prevention'
      ]
    }
  }
];

async function seedMedicalCases(prismaClient) {
  await prismaClient.medicalCase.deleteMany();
  await prismaClient.medicalCase.createMany({ data: cardiologyMedicalCases });
}

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
  // -------------------------
  // Core platform seed data
  // -------------------------
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

  // -------------------------
  // Cardiology case bank
  // -------------------------
  await seedMedicalCases(prisma);

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
