#!/usr/bin/env python3
"""سرور وب دانلود تصاویر Google Arts & Culture (فقط کتابخانه‌های استاندارد پایتون)."""
import html, json, os, re, time, urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 8765))
HOST = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
MAX_PAGE = 8 * 1024 * 1024      # حداکثر حجم صفحه‌ی HTML
MAX_IMAGE = 80 * 1024 * 1024    # حداکثر حجم هر تصویر
RATE_LIMIT, RATE_WINDOW = 40, 60  # حداکثر درخواست در هر دقیقه برای هر IP

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
IMG_RE = re.compile(r"(?:https?:)?//lh[0-9]\.googleusercontent\.com/[A-Za-z0-9_\-]{20,}")
OG_RE = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.I)
TITLE_RE = re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']*)["\']', re.I)
IMG_HOST = re.compile(r"^lh[0-9]\.googleusercontent\.com$")


def http_get(url, limit, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read(limit + 1)
                if len(data) > limit:
                    raise RuntimeError("حجم فایل بیش از حد مجاز است.")
                return data, r.headers
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"درخواست ناموفق بود: {last}")


def safe_name(text, fallback="image"):
    text = html.unescape(text or "").strip()
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:80] or fallback


def base_of(url):
    if url.startswith("//"):
        url = "https:" + url
    return url.split("=")[0]


def valid_page_url(url):
    p = urllib.parse.urlparse(url)
    h = p.hostname or ""
    return p.scheme in ("http", "https") and (h == "artsandculture.google.com" or h.endswith(".artsandculture.google.com"))


def valid_image_url(url):
    p = urllib.parse.urlparse(url)
    return p.scheme == "https" and bool(IMG_HOST.match(p.hostname or ""))


def extract_images(page_html, all_images=False):
    text = page_html.replace("\\u003d", "=").replace("\\/", "/")
    found = []
    og = OG_RE.search(text)
    if og:
        found.append(base_of(html.unescape(og.group(1))))
    if all_images or not found:
        found += [base_of(m.group(0)) for m in IMG_RE.finditer(text)]
    seen, unique = set(), []
    for u in found:
        if u not in seen and valid_image_url(u):
            seen.add(u)
            unique.append(u)
    return unique


def guess_ext(headers, data):
    ctype = (headers.get("Content-Type") or "").lower()
    if "png" in ctype or data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if "webp" in ctype or data[:4] == b"RIFF":
        return ".webp"
    if "gif" in ctype:
        return ".gif"
    return ".jpg"


_hits = {}


def rate_ok(ip):
    now = time.time()
    hits = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
    if len(hits) >= RATE_LIMIT:
        _hits[ip] = hits
        return False
    hits.append(now)
    _hits[ip] = hits
    if len(_hits) > 5000:  # جلوگیری از رشد حافظه
        _hits.clear()
    return True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _ip(self):
        fwd = self.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() or self.client_address[0]

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            with open(os.path.join(BASE_DIR, "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif parsed.path == "/healthz":
            self._send(200, "ok", "text/plain")
        elif parsed.path == "/api/download":
            if not rate_ok(self._ip()):
                return self._send(429, "درخواست‌ها زیاد است؛ کمی بعد دوباره تلاش کنید.", "text/plain; charset=utf-8")
            self._download(urllib.parse.parse_qs(parsed.query))
        else:
            self._send(404, "Not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/fetch":
            return self._send(404, "Not found", "text/plain")
        if not rate_ok(self._ip()):
            return self._json({"error": "درخواست‌ها زیاد است؛ کمی بعد دوباره تلاش کنید."}, 429)
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 10_000)
            req = json.loads(self.rfile.read(length) or b"{}")
            url = (req.get("url") or "").strip()
            if not valid_page_url(url):
                return self._json({"error": "لینک باید از artsandculture.google.com باشد."})
            raw, _ = http_get(url, MAX_PAGE)
            page = raw.decode("utf-8", errors="replace")
            t = TITLE_RE.search(page)
            title = safe_name(t.group(1) if t else urllib.parse.urlparse(url).path.rsplit("/", 1)[-1])
            images = extract_images(page, bool(req.get("all")))
            if not images:
                return self._json({"error": "تصویری در این صفحه پیدا نشد."})
            self._json({"title": title, "images": images})
        except Exception as e:
            self._json({"error": str(e)})

    def _download(self, q):
        base = (q.get("u") or [""])[0]
        name = safe_name((q.get("n") or ["image"])[0])
        if not valid_image_url(base):
            return self._send(400, "Bad image URL", "text/plain")
        try:
            data, headers = http_get(base + "=s0", MAX_IMAGE)
        except Exception as e:
            return self._send(502, str(e), "text/plain; charset=utf-8")
        ext = guess_ext(headers, data)
        ctype = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}.get(ext, "image/jpeg")
        fname = urllib.parse.quote(name + ext)
        self._send(200, data, ctype, {"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"})


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Running on http://{HOST}:{PORT}/")
    if not os.environ.get("PORT"):
        import threading, webbrowser
        threading.Timer(0.8, webbrowser.open, args=(f"http://127.0.0.1:{PORT}/",)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
