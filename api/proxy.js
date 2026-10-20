// ── Чат-бот: только со своих сайтов ────────────────────────────────────────
// POST (пересылка в Anthropic) принимается лишь с этих origin, остальным — 403.
// Дополнительные origin без правки кода: env CHAT_ALLOWED_ORIGINS="https://a.kz,https://b.kz"
// (после изменения env нужен новый деплой). GET (новости) открыт для всех.
const CHAT_ORIGINS = new Set([
  'https://taza-eco.vercel.app',
  'https://aktobe-eco.vercel.app',
  'https://atyrau-eco.vercel.app',
  ...(process.env.CHAT_ALLOWED_ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean),
]);

// Лимит чат-бота: не больше RATE_LIMIT вопросов с одного IP за RATE_WINDOW_MS.
// Счётчик живёт в памяти инстанса функции: от флуда защищает, строгой квотой не является
// (у разных инстансов свои счётчики, холодный старт обнуляет).
const RATE_LIMIT = 20;
const RATE_WINDOW_MS = 10 * 60 * 1000;
const _hits = new Map();

function clientIp(req) {
  const xff = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim();
  return String(req.headers['x-real-ip'] || '').trim() || xff || 'unknown';
}

// Возвращает 0, если запрос можно пропустить, иначе — сколько секунд ждать.
function rateLimitWait(ip, now = Date.now()) {
  const recent = (_hits.get(ip) || []).filter(t => now - t < RATE_WINDOW_MS);
  if (recent.length >= RATE_LIMIT) {
    _hits.set(ip, recent);
    return Math.ceil((recent[0] + RATE_WINDOW_MS - now) / 1000);
  }
  recent.push(now);
  _hits.set(ip, recent);
  if (_hits.size > 5000) {
    for (const [k, v] of _hits) if (now - v[v.length - 1] >= RATE_WINDOW_MS) _hits.delete(k);
  }
  return 0;
}

function setOpenCors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

function setChatCors(res, origin) {
  res.setHeader('Access-Control-Allow-Origin', origin);
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Vary', 'Origin');
}

export default async function handler(req, res) {
  const origin = String(req.headers.origin || '');

  if (req.method === 'OPTIONS') {
    const wantsPost = String(req.headers['access-control-request-method'] || '').toUpperCase() === 'POST';
    if (!wantsPost) { setOpenCors(res); return res.status(200).end(); }
    res.setHeader('Vary', 'Origin');
    if (!CHAT_ORIGINS.has(origin)) return res.status(403).end();
    setChatCors(res, origin);
    return res.status(200).end();
  }

  // ── RSS / HTML proxy ─────────────────────────────────────────────────────
  if (req.method === 'GET' && req.query.rss) {
    setOpenCors(res);
    const url = decodeURIComponent(req.query.rss);
    const allowed = [
      'tengrinews.kz', 'kapital.kz', '24.kz', 'kursiv.kz', 'kz.kursiv.media',
      'primeminister.kz', 'lsm.kz', 'gov.kz', 'rsshub.app',
      't.me',          // Telegram preview pages (t.me/s/<channel>)
      'kazhydromet.kz' // HTML-парсинг новостной ленты Казгидромета
    ];
    if (!allowed.some(d => url.includes(d))) {
      return res.status(403).json({ error: 'Domain not allowed' });
    }
    try {
      const r = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; EcoDashboard/1.0)',
          'Accept': 'application/rss+xml, application/xml, text/xml, text/html, */*'
        },
        redirect: 'follow',
        signal: AbortSignal.timeout(10000)
      });
      if (!r.ok) return res.status(r.status).json({ error: `Upstream ${r.status}` });
      const body = await r.text();
      const isHtml = url.includes('t.me') || url.includes('kazhydromet.kz');
      res.setHeader('Content-Type',
        isHtml ? 'text/html; charset=utf-8' : 'application/xml; charset=utf-8');
      res.setHeader('Cache-Control', 's-maxage=900, stale-while-revalidate=1800');
      return res.status(200).send(body);
    } catch (e) {
      return res.status(500).json({ error: e.message });
    }
  }

  // ── Anthropic proxy ──────────────────────────────────────────────────────
  if (req.method === 'POST') {
    res.setHeader('Vary', 'Origin');
    if (!CHAT_ORIGINS.has(origin)) {
      return res.status(403).json({ error: { type: 'forbidden', message: 'Origin not allowed' } });
    }
    setChatCors(res, origin);
    const wait = rateLimitWait(clientIp(req));
    if (wait) {
      res.setHeader('Retry-After', String(wait));
      return res.status(429).json({ error: { type: 'rate_limit',
        message: `Слишком много вопросов с вашего адреса. Повторите через ${Math.ceil(wait / 60)} мин.` } });
    }
    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) return res.status(500).json({ error: 'No ANTHROPIC_API_KEY' });
    try {
      const r = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' },
        body: JSON.stringify(req.body)
      });
      const data = await r.json();
      return res.status(200).json(data);
    } catch (e) {
      return res.status(500).json({ error: e.message });
    }
  }

  setOpenCors(res);
  return res.status(405).json({ error: 'Method not allowed' });
}
