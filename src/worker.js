// سرور دانلود تصاویر Google Arts & Culture برای Cloudflare Workers
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";
const IMG_RE = /(?:https?:)?\/\/lh[0-9]\.googleusercontent\.com\/[A-Za-z0-9_\-]{20,}/g;
const OG_RE = /<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/i;
const TITLE_RE = /<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']*)["']/i;

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json; charset=utf-8" } });

function unescapeHtml(s) {
  return (s || "")
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(+d))
    .replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
}

function safeName(text, fallback = "image") {
  const t = unescapeHtml(text).replace(/[\\/:*?"<>|\r\n\t]+/g, " ").replace(/\s+/g, " ").trim().replace(/^[ .]+|[ .]+$/g, "");
  return t.slice(0, 80) || fallback;
}

function baseOf(url) {
  if (url.startsWith("//")) url = "https:" + url;
  return url.split("=")[0];
}

function validPageUrl(url) {
  try {
    const u = new URL(url);
    return ["http:", "https:"].includes(u.protocol) &&
      (u.hostname === "artsandculture.google.com" || u.hostname.endsWith(".artsandculture.google.com"));
  } catch { return false; }
}

function validImageUrl(url) {
  try {
    const u = new URL(url);
    return u.protocol === "https:" && /^lh[0-9]\.googleusercontent\.com$/.test(u.hostname);
  } catch { return false; }
}

function extractImages(pageHtml, all) {
  const text = pageHtml.replace(/\\u003d/g, "=").replace(/\\\//g, "/");
  const found = [];
  const og = OG_RE.exec(text);
  if (og) found.push(baseOf(unescapeHtml(og[1])));
  if (all || !found.length) for (const m of text.matchAll(IMG_RE)) found.push(baseOf(m[0]));
  return [...new Set(found)].filter(validImageUrl);
}

async function get(url, tries = 3) {
  let last;
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url, { headers: { "User-Agent": UA, "Accept-Language": "en" } });
      if (r.ok) return r;
      last = new Error("HTTP " + r.status);
    } catch (e) { last = e; }
    await new Promise(res => setTimeout(res, 800 * (i + 1)));
  }
  throw new Error("درخواست ناموفق بود: " + last.message);
}

async function handleFetch(request) {
  try {
    const req = await request.json();
    const url = String(req.url || "").trim();
    if (!validPageUrl(url)) return json({ error: "لینک باید از artsandculture.google.com باشد." });
    const page = await (await get(url)).text();
    const t = TITLE_RE.exec(page);
    const title = safeName(t ? t[1] : new URL(url).pathname.split("/").pop());
    const images = extractImages(page, !!req.all);
    if (!images.length) return json({ error: "تصویری در این صفحه پیدا نشد." });
    return json({ title, images });
  } catch (e) {
    return json({ error: e.message });
  }
}

async function handleDownload(url) {
  const base = url.searchParams.get("u") || "";
  const name = safeName(url.searchParams.get("n") || "image");
  if (!validImageUrl(base)) return new Response("Bad image URL", { status: 400 });
  try {
    const up = await get(base + "=s0");
    const type = (up.headers.get("Content-Type") || "image/jpeg").toLowerCase();
    const ext = type.includes("png") ? ".png" : type.includes("webp") ? ".webp" : type.includes("gif") ? ".gif" : ".jpg";
    return new Response(up.body, {
      headers: {
        "Content-Type": type,
        "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(name + ext)}`,
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch (e) {
    return new Response(e.message, { status: 502 });
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api/fetch" && request.method === "POST") return handleFetch(request);
    if (url.pathname === "/api/download" && request.method === "GET") return handleDownload(url);
    return env.ASSETS.fetch(request);
  },
};
