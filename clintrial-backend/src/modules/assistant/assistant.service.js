import { request as undiciRequest } from 'undici';
import { env } from '../../utils/env.js';

export async function callAssistant({ sessionId, question, historySummary, forceLocal }) {
  const url = `${env.ASSISTANT_BASE_URL}/${env.ASSISTANT_LAPTOP_CODE}/${env.ASSISTANT_MODE}/${sessionId}`;
  const body = {
    question,
    history_summary: historySummary || '',
    force_local: !!forceLocal
  };

  const { statusCode, body: resBody } = await undiciRequest(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body)
  });

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
