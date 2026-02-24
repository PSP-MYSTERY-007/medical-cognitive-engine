import bcrypt from 'bcryptjs';
import crypto from 'crypto';
import dayjs from 'dayjs';
import { prisma } from '../../services/prisma.js';
import { env } from '../../utils/env.js';

function sha256(input) {
  return crypto.createHash('sha256').update(input).digest('hex');
}

export function makeOpaqueToken() {
  return crypto.randomBytes(48).toString('base64url');
}

export async function register({ fullName, email, password, universityCode, role }) {
  const normalizedEmail = email.trim().toLowerCase();

  if (env.UNIVERSITY_EMAIL_DOMAIN) {
    const ok = normalizedEmail.endsWith('@' + env.UNIVERSITY_EMAIL_DOMAIN.toLowerCase());
    if (!ok) {
      throw Object.assign(new Error('Email domain not allowed'), { statusCode: 400 });
    }
  }

  const exists = await prisma.user.findUnique({ where: { email: normalizedEmail } });
  if (exists) {
    throw Object.assign(new Error('Email already registered'), { statusCode: 409 });
  }

  let universityId = null;
  if (universityCode) {
    const uni = await prisma.university.findUnique({ where: { uniqueCode: universityCode } });
    if (!uni) {
      throw Object.assign(new Error('Invalid university code'), { statusCode: 400 });
    }
    universityId = uni.id;
  }

  const passwordHash = await bcrypt.hash(password, 12);
  const user = await prisma.user.create({
    data: {
      fullName,
      email: normalizedEmail,
      passwordHash,
      role: role || 'STUDENT',
      universityId
    },
    select: { id: true, fullName: true, email: true, role: true, universityId: true, createdAt: true }
  });

  return user;
}

export async function verifyPassword(user, password) {
  return bcrypt.compare(password, user.passwordHash);
}

export async function issueTokens(fastify, userId, role) {
  const accessToken = fastify.jwt.sign(
    { sub: userId, role },
    { expiresIn: env.ACCESS_TOKEN_TTL_SECONDS }
  );

  const refreshToken = makeOpaqueToken();
  const refreshTokenHash = sha256(refreshToken);
  const expiresAt = dayjs().add(env.REFRESH_TOKEN_TTL_DAYS, 'day').toDate();

  await prisma.refreshToken.create({
    data: {
      userId,
      tokenHash: refreshTokenHash,
      expiresAt
    }
  });

  return { accessToken, refreshToken, expiresAt };
}

export async function login(fastify, { email, password }) {
  const normalizedEmail = email.trim().toLowerCase();
  const user = await prisma.user.findUnique({ where: { email: normalizedEmail } });
  if (!user) {
    throw Object.assign(new Error('Invalid credentials'), { statusCode: 401 });
  }

  const ok = await verifyPassword(user, password);
  if (!ok) {
    throw Object.assign(new Error('Invalid credentials'), { statusCode: 401 });
  }

  const tokens = await issueTokens(fastify, user.id, user.role);

  return {
    user: { id: user.id, fullName: user.fullName, email: user.email, role: user.role, universityId: user.universityId },
    tokens
  };
}

export async function rotateRefreshToken(fastify, { refreshToken }) {
  const tokenHash = sha256(refreshToken);
  const record = await prisma.refreshToken.findFirst({ where: { tokenHash }, include: { user: true } });
  if (!record || record.revokedAt) {
    throw Object.assign(new Error('Invalid refresh token'), { statusCode: 401 });
  }
  if (record.expiresAt < new Date()) {
    throw Object.assign(new Error('Refresh token expired'), { statusCode: 401 });
  }

  // revoke old token (rotation)
  await prisma.refreshToken.update({ where: { id: record.id }, data: { revokedAt: new Date() } });

  const tokens = await issueTokens(fastify, record.userId, record.user.role);

  return {
    user: { id: record.user.id, fullName: record.user.fullName, email: record.user.email, role: record.user.role, universityId: record.user.universityId },
    tokens
  };
}

export async function logout({ refreshToken }) {
  const tokenHash = sha256(refreshToken);
  await prisma.refreshToken.updateMany({ where: { tokenHash, revokedAt: null }, data: { revokedAt: new Date() } });
}

export async function requestPasswordReset({ email }) {
  const normalizedEmail = email.trim().toLowerCase();
  const user = await prisma.user.findUnique({ where: { email: normalizedEmail } });
  if (!user) {
    // Don't reveal whether user exists
    return { ok: true };
  }

  const token = makeOpaqueToken();
  const tokenHash = sha256(token);
  const expiresAt = dayjs().add(30, 'minute').toDate();

  await prisma.passwordResetToken.create({ data: { userId: user.id, tokenHash, expiresAt } });

  // In production, email the token. For dev, return it.
  return { ok: true, token };
}

export async function resetPassword({ token, newPassword }) {
  const tokenHash = sha256(token);
  const record = await prisma.passwordResetToken.findFirst({ where: { tokenHash }, include: { user: true } });
  if (!record || record.usedAt) {
    throw Object.assign(new Error('Invalid reset token'), { statusCode: 400 });
  }
  if (record.expiresAt < new Date()) {
    throw Object.assign(new Error('Reset token expired'), { statusCode: 400 });
  }

  const passwordHash = await bcrypt.hash(newPassword, 12);
  await prisma.user.update({ where: { id: record.userId }, data: { passwordHash } });
  await prisma.passwordResetToken.update({ where: { id: record.id }, data: { usedAt: new Date() } });

  // Revoke all refresh tokens on password reset
  await prisma.refreshToken.updateMany({ where: { userId: record.userId, revokedAt: null }, data: { revokedAt: new Date() } });

  return { ok: true };
}
