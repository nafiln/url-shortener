# URL Shortener — SPEC

## Overview
A minimal URL shortener with SQLite backend, redirect endpoint, HTML form, and 404 handling.

## Routes

| Method | Path | Behavior |
|---|---|---|
| GET | `/` | Serve an HTML form where users paste a long URL and submit |
| POST | `/shorten` | Accept `url` form field, store in SQLite, return the short code |
| GET | `/{code}` | 301 redirect to stored URL; 404 if code unknown |

## Functional Requirements

1. **POST /shorten** — Accept `url` (form-encoded or JSON). Auto-prepend `https://` if the submitted URL has no scheme (`://`). Generate a short code (6-char alphanumeric, URL-safe). Return `{"short_code": "abc123"}`.
2. **GET /{code}** — Look up code in SQLite. If found, 301 redirect to the original URL. If not found, return 404 with `{"error": "Short code not found"}`.
3. **GET /** — Return an HTML page with minimal styling, a form input for the URL, and a submit button. After submission, display the short URL.
4. **404 for unknown codes** — Any `GET /{code}` that doesn't match returns a JSON 404, not a catch-all.

## Data Model

```sql
CREATE TABLE IF NOT EXISTS urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    url TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_code ON urls(code);
```

## Tech Stack

- **Language:** Python 3.13+ with just stdlib (`http.server`, `sqlite3`, `json`, `urllib`, `string`)
- **Database:** SQLite (file: `urls.db`, auto-created)
- **No framework, no dependencies** — single self-contained file

## File Structure

```
url-shortener/
├── server.py          # Main application
├── urls.db            # SQLite database (auto-created, gitignored)
├── .gitignore
├── PLUMBING.md        # Existing placeholder
└── SPEC.md            # This file
```

## Constraints

- No external packages (stdlib only)
- Handle concurrent requests safely — use threading lock on SQLite writes
- Short codes: 6 chars, alphanumeric, random, retry on collision
- Graceful shutdown (save db, close socket)
- Port 8080 by default, configurable via `PORT` env var
