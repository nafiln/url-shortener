#!/usr/bin/env python3
"""
Integration tests for the URL shortener.
Start the server first, then run: python3 test_server.py
"""

import json
import subprocess
import sys
import urllib.error
import urllib.request
import urllib.parse

BASE = "http://localhost:8080"


def request(method, path, data=None, headers=None):
    url = f"{BASE}{path}"
    body = None
    if data:
        if headers and "application/json" in headers.get("Content-Type", ""):
            body = json.dumps(data).encode()
        else:
            body = urllib.parse.urlencode(data).encode()

    req = urllib.request.Request(url, data=body, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)

    try:
        resp = urllib.request.urlopen(req)
        return resp.status, resp.read().decode(), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers


def test_get_form():
    status, body, _ = request("GET", "/")
    assert status == 200
    assert "<form" in body
    print("  ✅ GET / returns HTML form")


def test_shorten_form():
    status, body, _ = request("POST", "/shorten", {"url": "https://example.com"})
    assert status == 200
    data = json.loads(body)
    assert "short_code" in data
    code = data["short_code"]
    assert len(code) == 6
    print(f"  ✅ POST /shorten (form) → {code}")


def test_shorten_json():
    status, body, _ = request("POST", "/shorten",
                              {"url": "https://httpbin.org"},
                              {"Content-Type": "application/json"})
    assert status == 200
    data = json.loads(body)
    assert "short_code" in data
    print(f"  ✅ POST /shorten (JSON) → {data['short_code']}")


def test_shorten_no_scheme():
    status, body, _ = request("POST", "/shorten", {"url": "example.org"})
    data = json.loads(body)
    code = data["short_code"]

    # Use a custom opener that does NOT follow redirects
    import http.client

    conn = http.client.HTTPConnection("localhost", 8080)
    conn.request("GET", f"/{code}")
    resp = conn.getresponse()
    assert resp.status == 301, f"Expected 301, got {resp.status}"
    location = resp.getheader("Location", "")
    assert location == "https://example.org", f"Expected https://example.org, got {location}"
    conn.close()
    print(f"  ✅ POST /shorten (no scheme) → auto-prepended https://")


def test_redirect():
    import http.client

    # Shorten a known URL
    status, body, _ = request("POST", "/shorten", {"url": "https://example.com/abc"})
    code = json.loads(body)["short_code"]

    # Check redirect using raw http.client
    conn = http.client.HTTPConnection("localhost", 8080)
    conn.request("GET", f"/{code}")
    resp = conn.getresponse()
    assert resp.status == 301, f"Expected 301, got {resp.status}"
    assert resp.getheader("Location") == "https://example.com/abc"
    conn.close()
    print(f"  ✅ GET /{code} → 301 to correct URL")


def test_404():
    status, body, _ = request("GET", "/NONEXIST")
    assert status == 404
    data = json.loads(body)
    assert "error" in data
    print("  ✅ GET /NONEXIST → 404 JSON")


def test_missing_url():
    status, body, _ = request("POST", "/shorten", {})
    assert status == 400
    print("  ✅ POST /shorten (no url) → 400")


if __name__ == "__main__":
    tests = [
        test_get_form,
        test_shorten_form,
        test_shorten_json,
        test_shorten_no_scheme,
        test_redirect,
        test_404,
        test_missing_url,
    ]

    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  ❌ {t.__name__}: {e}")
            raise

    print(f"\n{'='*40}\n{passed}/{len(tests)} tests passed")
    sys.exit(0 if passed == len(tests) else 1)
