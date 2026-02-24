import dotenv from 'dotenv';

dotenv.config();

function required(name) {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env var: ${name}`);
  return v;
}

export const env = {
  NODE_ENV: process.env.NODE_ENV || 'development',
  PORT: parseInt(process.env.PORT || '3000', 10),
  HOST: process.env.HOST || '0.0.0.0',
  DATABASE_URL: required('DATABASE_URL'),
  JWT_ACCESS_SECRET: required('JWT_ACCESS_SECRET'),
  JWT_REFRESH_SECRET: required('JWT_REFRESH_SECRET'),
  ACCESS_TOKEN_TTL_SECONDS: parseInt(process.env.ACCESS_TOKEN_TTL_SECONDS || '900', 10),
  REFRESH_TOKEN_TTL_DAYS: parseInt(process.env.REFRESH_TOKEN_TTL_DAYS || '30', 10),
  UNIVERSITY_EMAIL_DOMAIN: process.env.UNIVERSITY_EMAIL_DOMAIN || '',
  ASSISTANT_BASE_URL: process.env.ASSISTANT_BASE_URL || 'http://127.0.0.1:8000',
  ASSISTANT_LAPTOP_CODE: process.env.ASSISTANT_LAPTOP_CODE || 'STUDENT_LAPTOP_01',
  ASSISTANT_MODE: process.env.ASSISTANT_MODE || 'chat',
  REDIS_URL: process.env.REDIS_URL || 'redis://127.0.0.1:6379',
  USE_REDIS: String(process.env.USE_REDIS || 'false').toLowerCase() === 'true'
};
