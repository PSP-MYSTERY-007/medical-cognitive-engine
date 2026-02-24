import Redis from 'ioredis';
import { env } from '../utils/env.js';

let redis = null;

export function getRedis() {
  if (!env.USE_REDIS) return null;
  if (redis) return redis;
  redis = new Redis(env.REDIS_URL, { maxRetriesPerRequest: 2 });
  redis.on('error', (err) => {
    console.error('Redis error:', err.message);
  });
  return redis;
}
