import { request as undiciRequest } from 'undici';
import { env } from '../../utils/env.js';

export async function callAssistant({ sessionId, question, historySummary, forceLocal }) {
  const url = `${env.ASSISTANT_BASE_URL}/${env.ASSISTANT_LAPTOP_CODE}/${env.ASSISTANT_MODE}/${sessionId}`;
  const body = {
    question,
    history_summary: historySummary || '',
    force_local: !!forceLocal
  };

  let statusCode;
  let resBody;
  try {
    ({ statusCode, body: resBody } = await undiciRequest(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body)
    }));
  } catch (err) {
    const connectivityCodes = new Set([
      'ECONNREFUSED',
      'ECONNRESET',
      'ENOTFOUND',
      'EHOSTUNREACH',
      'ETIMEDOUT',
      'UND_ERR_CONNECT_TIMEOUT'
    ]);
    if (connectivityCodes.has(err?.code)) {
      throw Object.assign(
        new Error(
          `Assistant service unavailable (${env.ASSISTANT_BASE_URL}). Start the Python backend on port 8000 or update ASSISTANT_BASE_URL.`
        ),
        { statusCode: 503 }
      );
    }
    throw err;
  }

  const text = await resBody.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    throw Object.assign(new Error(`Assistant returned non-JSON (${statusCode}): ${text.slice(0, 200)}`), { statusCode: 502 });
  }

  if (statusCode >= 400) {
    const msg = json?.detail || json?.error || 'Assistant error';
    throw Object.assign(new Error(msg), { statusCode: 502 });
  }

  return json.answer || '';
}
