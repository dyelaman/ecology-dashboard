export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });

  const { channel } = req.query;
  const ALLOWED = {
    kozachkow: 'Kozachkov Offside',
    tengrinews: 'Tengrinews KZ',
  };

  if (!channel || !ALLOWED[channel]) {
    return res.status(403).json({ error: 'Channel not allowed' });
  }

  try {
    const r = await fetch(`https://t.me/s/${channel}`, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
      },
      signal: AbortSignal.timeout(10000),
    });

    if (!r.ok) return res.status(r.status).json({ error: `Upstream ${r.status}` });

    const html = await r.text();
    const posts = parseTgPosts(html, channel, ALLOWED[channel]);

    res.setHeader('Cache-Control', 's-maxage=900, stale-while-revalidate=1800');
    return res.status(200).json({ channel, displayName: ALLOWED[channel], posts });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}

function stripHtml(html) {
  return html
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<a\s[^>]*href="([^"]*)"[^>]*>(.*?)<\/a>/gi, '$2')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&nbsp;/g, ' ')
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n))
    .replace(/\s+/g, ' ')
    .trim();
}

function parseTgPosts(html, channel, displayName) {
  const posts = [];

  // Each message block starts with this class
  const blocks = html.split('<div class="tgme_widget_message_wrap');

  for (let i = 1; i < blocks.length; i++) {
    const block = blocks[i];

    // Post ID from data-post="channel/ID"
    const idMatch = block.match(/data-post="[^/]+\/(\d+)"/);
    if (!idMatch) continue;
    const id = idMatch[1];

    // Message text div — capture content until the closing tag pattern
    const textMatch = block.match(/<div class="tgme_widget_message_text[^"]*"[^>]*>([\s\S]*?)<\/div>\s*(?:<\/div|<div class="tgme_widget_message_footer)/);
    if (!textMatch) continue;
    const text = stripHtml(textMatch[1]);
    if (!text || text.length < 15) continue;

    // ISO datetime
    const dateMatch = block.match(/datetime="([^"]+)"/);
    const isoDate = dateMatch ? dateMatch[1] : '';
    let date = '';
    if (isoDate) {
      try {
        date = new Date(isoDate).toLocaleDateString('ru-RU', {
          day: '2-digit', month: '2-digit', year: 'numeric'
        });
      } catch (_) { date = ''; }
    }

    posts.push({
      id,
      text: text.slice(0, 600),
      isoDate,
      date,
      url: `https://t.me/${channel}/${id}`,
      source: 'telegram',
      channel,
      displayName,
    });
  }

  // Newest first
  posts.sort((a, b) => parseInt(b.id, 10) - parseInt(a.id, 10));
  return posts.slice(0, 20);
}
