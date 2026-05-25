export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();

  // ── RSS / HTML proxy ─────────────────────────────────────────────────────
  if (req.method === 'GET' && req.query.rss) {
    const url = decodeURIComponent(req.query.rss);
    const allowed = [
      'tengrinews.kz', 'kapital.kz', '24.kz', 'kursiv.kz', 'kz.kursiv.media',
      'primeminister.kz', 'lsm.kz', 'gov.kz', 'rsshub.app',
      't.me'   // Telegram preview pages (t.me/s/<channel>)
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
      const isTelegram = url.includes('t.me');
      res.setHeader('Content-Type',
        isTelegram ? 'text/html; charset=utf-8' : 'application/xml; charset=utf-8');
      res.setHeader('Cache-Control', 's-maxage=900, stale-while-revalidate=1800');
      return res.status(200).send(body);
    } catch (e) {
      return res.status(500).json({ error: e.message });
    }
  }

  // ── Anthropic proxy ──────────────────────────────────────────────────────
  if (req.method === 'POST') {
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

  return res.status(405).json({ error: 'Method not allowed' });
}
