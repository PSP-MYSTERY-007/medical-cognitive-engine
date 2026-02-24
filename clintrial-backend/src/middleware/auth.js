export async function requireAuth(request, reply) {
  try {
    await request.jwtVerify();
  } catch (err) {
    return reply.code(401).send({ error: 'Unauthorized' });
  }
}

export function requireRole(roles) {
  return async function (request, reply) {
    await requireAuth(request, reply);
    if (reply.sent) return;
    const role = request.user?.role;
    if (!role || !roles.includes(role)) {
      return reply.code(403).send({ error: 'Forbidden' });
    }
  };
}
