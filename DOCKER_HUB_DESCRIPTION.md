# Thule Homepage

**Personalized start page with card grid, search, background images, and Gnome 42 aesthetics.**

---

## Quick Start

```bash
docker run -d -p 127.0.0.1:8000:8000 -v thule-data:/app/data thuleseeker/thule:latest
```

Open [http://localhost:8000](http://localhost:8000).

The port is bound to loopback: the app has no accounts. For network access set `AUTH_TOKEN` and use a reverse proxy with TLS.

## Persistent Data

```bash
docker run -d -p 127.0.0.1:8000:8000 \
  -e AUTH_TOKEN="$(openssl rand -hex 32)" \
  -v thule-data:/app/data thuleseeker/thule:latest
```

The container runs as an unprivileged user (`uid 10001`). With a named volume the ownership is preserved automatically; with a bind mount the host directory must be owned by `10001:10001`.

## Docker Compose

```yaml
services:
  homepage:
    image: thuleseeker/thule:latest
    container_name: thule-homepage
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      # Must be writable by uid 10001: sudo chown -R 10001:10001 homepage-data
      - ./homepage-data:/app/data
    environment:
      - TZ=Europe/Moscow
      # - AUTH_TOKEN=change-me
    restart: unless-stopped
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

## Features

- **Card Grid** — customizable cards with icons, URLs, and sizes (1×1, 2×1, 1×2, 2×2)
- **Open Mode** — per-card choice to open the link in a new tab or the same tab
- **Drag-and-Drop** — reorder cards via drag & drop
- **Search** — built-in search bar with autocomplete (Google, DuckDuckGo, Bing, Yandex)
- **Background Images** — upload with drag-and-drop, blur control
- **Light/Dark Theme** — toggle with persistence
- **Import/Export** — transactional JSON backup and restore
- **Auto Favicon** — automatic icon fetching from websites (SSRF protection, redirect validation)
- **Asset Caching** — icons & static assets served with `Cache-Control`
- **Responsive** — desktop, tablet, and mobile support
- **Optional Auth** — set `AUTH_TOKEN` to protect every API endpoint

## Architecture

| Component | Technology |
|-----------|------------|
| Backend | FastAPI + uvicorn + SQLite (WAL) |
| Frontend | Vanilla JS + CSS Grid |
| Image Storage | `/app/data/uploads/` |

## Ports

| Port | Protocol | Description |
|------|----------|-------------|
| 8000 | HTTP | Web UI & API |

## Volumes

| Path | Description |
|------|-------------|
| `/app/data` | SQLite database + uploaded images |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Application port |
| `DATABASE_PATH` | `/app/data/homepage.db` | SQLite database path |
| `UPLOADS_DIR` | `/app/data/uploads` | Uploaded images directory |
| `AUTH_TOKEN` | — | Shared API token; when set, authentication is required |
| `APP_VERSION` | `1.2.1` | Version reported by `/api/health` |
| `LOG_LEVEL` | `INFO` | Logging level |

## Health Check

```
GET http://localhost:8000/api/health
```

Response: `{"status": "healthy", "version": "1.2.1"}`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check (always public) |
| `GET` | `/api/settings` | Get settings |
| `PUT` | `/api/settings` | Partial settings update |
| `GET` | `/api/cards` | Get all cards |
| `POST` | `/api/cards` | Create card |
| `PUT` | `/api/cards/{id}` | Update card |
| `DELETE` | `/api/cards/{id}` | Delete card |
| `POST` | `/api/cards/reorder` | Reorder cards |
| `GET` | `/api/full-data` | Get settings + cards |
| `POST` | `/api/import` | Transactional import (replaces all cards) |
| `POST` | `/api/upload` | Upload image |
| `GET` | `/api/uploads/{filename}` | Get uploaded image |
| `DELETE` | `/api/upload/{filename}` | Delete uploaded image |
| `POST` | `/api/fetch-icon` | Fetch favicon from URL |

All `/api/*` endpoints except `GET /api/health` require `X-Auth-Token: <token>` (or `Authorization: Bearer <token>`) when `AUTH_TOKEN` is set.

## Tags

| Tag | Description |
|-----|-------------|
| `latest` | Latest stable build |
| `1.2.1` | Security hardening, data-integrity fixes, tests, documentation |
| `1.1.0` | Per-card open mode, asset caching, frontend stability fixes |
| `1.0.0` | Initial release |

## Source Code

[GitHub — Nezhirn/thule-homepage](https://github.com/Nezhirn/thule-homepage)

## License

GNU General Public License v3.0 — see the `LICENSE` file.
