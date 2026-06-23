#!/usr/bin/env python3
"""
URL Shortener — single-file stdlib Python implementation.
POST /shorten  → returns short code
GET /{code}    → 301 redirect (404 if unknown)
GET /          → HTML form

Usage: python server.py [PORT]
"""

import http.server
import json
import os
import random
import sqlite3
import string
import threading
import urllib.parse

PORT = int(os.environ.get("PORT", 8080))
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "urls.db")
CODE_LENGTH = 6
CODE_CHARS = string.ascii_letters + string.digits

# ── Database ──────────────────────────────────────────────────────────────

_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.execute("PRAGMA journal_mode=WAL")
_conn.execute("PRAGMA synchronous=NORMAL")
_conn.execute(
    """CREATE TABLE IF NOT EXISTS urls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        url TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )"""
)
_conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_code ON urls(code)")
_conn.commit()

_write_lock = threading.Lock()


def _init_db():
    """Ensure the DB is set up. Safe to call at import time."""
    pass


def _generate_code() -> str:
    return "".join(random.choices(CODE_CHARS, k=CODE_LENGTH))


def _store_url(url: str) -> str:
    """Insert a URL with a unique short code. Retry on collision."""
    url = _normalize_url(url)
    for _ in range(10):
        code = _generate_code()
        with _write_lock:
            try:
                _conn.execute(
                    "INSERT INTO urls (code, url) VALUES (?, ?)", (code, url)
                )
                _conn.commit()
                return code
            except sqlite3.IntegrityError:
                continue
    raise RuntimeError("Could not generate unique short code")


def _lookup_code(code: str) -> str | None:
    cursor = _conn.execute("SELECT url FROM urls WHERE code = ?", (code,))
    row = cursor.fetchone()
    return row[0] if row else None


def _normalize_url(url: str) -> str:
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    return url


# ── HTTP Handler ──────────────────────────────────────────────────────────


class ShortenerHandler(http.server.BaseHTTPRequestHandler):
    # Silence default logging (we log explicitly)
    def log_message(self, format, *args):
        pass

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, html: str):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> str:
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return self.rfile.read(length).decode("utf-8")
        return ""

    def _parse_form(self, body: str) -> dict:
        """Parse both form-encoded and JSON bodies."""
        ct = self.headers.get("Content-Type", "")
        if "application/json" in ct:
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {}
        # Default: form-encoded
        return dict(urllib.parse.parse_qsl(body))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/":
            self._send_html(200, HTML_FORM)
            return

        # Try short code lookup
        code = parsed.path.lstrip("/")
        if not code or "/" in code:
            self._send_json(404, {"error": "Not found"})
            return

        url = _lookup_code(code)
        if url is None:
            self._send_json(404, {"error": "Short code not found"})
            return

        self.send_response(301)
        self.send_header("Location", url)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/shorten":
            body = self._read_body()
            data = self._parse_form(body)
            url = data.get("url", "").strip()
            if not url:
                self._send_json(400, {"error": "Missing 'url' field"})
                return

            code = _store_url(url)
            self._send_json(200, {"short_code": code})
            return

        self._send_json(404, {"error": "Not found"})

    def do_HEAD(self):
        """Respond without body for health checks."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()


HTML_FORM = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>URL Shortener</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      display: flex; justify-content: center; align-items: center;
      min-height: 100vh; margin: 0; background: #f5f7fa; color: #1a1a2e;
    }
    .card {
      background: #fff; border-radius: 12px; padding: 2.5rem;
      box-shadow: 0 4px 24px rgba(0,0,0,0.08); width: 100%; max-width: 480px;
    }
    h1 { margin: 0 0 0.5rem; font-size: 1.5rem; font-weight: 600; }
    p { margin: 0 0 1.5rem; color: #64748b; font-size: 0.9rem; }
    input[type="url"], input[type="text"] {
      width: 100%; padding: 0.75rem 1rem; border: 1px solid #e2e8f0;
      border-radius: 8px; font-size: 1rem; outline: none; transition: border-color 0.15s;
    }
    input:focus { border-color: #6366f1; }
    button {
      width: 100%; margin-top: 0.75rem; padding: 0.75rem; border: none;
      border-radius: 8px; background: #6366f1; color: #fff; font-size: 1rem;
      font-weight: 500; cursor: pointer; transition: background 0.15s;
    }
    button:hover { background: #4f46e5; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    #result { margin-top: 1rem; display: none; }
    #result a {
      display: block; margin-top: 0.5rem; padding: 0.5rem; background: #f0fdf4;
      border: 1px solid #bbf7d0; border-radius: 6px; text-align: center;
      color: #15803d; text-decoration: none; font-weight: 500; word-break: break-all;
    }
    #error { margin-top: 1rem; color: #dc2626; display: none; font-size: 0.875rem; }
  </style>
</head>
<body>
  <div class="card">
    <h1>🔗 URL Shortener</h1>
    <p>Paste a long URL to get a short, shareable link.</p>
    <form id="shorten-form">
      <input type="url" id="url-input" placeholder="https://example.com/very/long/url" required>
      <button type="submit" id="submit-btn">Shorten</button>
    </form>
    <div id="result">
      Short URL: <a id="short-url" href="#" target="_blank"></a>
    </div>
    <div id="error"></div>
  </div>
  <script>
    const form = document.getElementById('shorten-form');
    const input = document.getElementById('url-input');
    const btn = document.getElementById('submit-btn');
    const result = document.getElementById('result');
    const shortUrl = document.getElementById('short-url');
    const errorDiv = document.getElementById('error');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      result.style.display = 'none';
      errorDiv.style.display = 'none';
      btn.disabled = true;
      btn.textContent = 'Shortening...';

      try {
        const resp = await fetch('/shorten', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: 'url=' + encodeURIComponent(input.value)
        });
        const data = await resp.json();
        if (resp.ok) {
          const short = window.location.origin + '/' + data.short_code;
          shortUrl.href = short;
          shortUrl.textContent = short;
          result.style.display = 'block';
        } else {
          errorDiv.textContent = data.error || 'Something went wrong';
          errorDiv.style.display = 'block';
        }
      } catch (err) {
        errorDiv.textContent = 'Network error';
        errorDiv.style.display = 'block';
      } finally {
        btn.disabled = false;
        btn.textContent = 'Shorten';
      }
    });
  </script>
</body>
</html>
"""


# ── Server Entrypoint ─────────────────────────────────────────────────────


def create_server() -> http.server.HTTPServer:
    server = http.server.HTTPServer(("0.0.0.0", PORT), ShortenerHandler)
    return server


def run():
    server = create_server()
    print(f"URL Shortener listening on http://0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    run()
