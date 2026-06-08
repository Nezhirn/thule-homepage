# Thule Homepage

**Personalized start page with card grid, search, background images, and Gnome 42 aesthetics.**

---

## Quick Start

```bash
docker run -d -p 8000:8000 thuleseeker/thule:latest
```

Open [http://localhost:8000](http://localhost:8000).

## Persistent Data

```bash
docker run -d -p 8000:8000 -v thule-data:/app/data thuleseeker/thule:latest
```

## Docker Compose

```yaml
services:
  homepage:
    image: thuleseeker/thule:latest
    container_name: thule-homepage
    ports:
      - "8000:8000"
    volumes:
      - thule-data:/app/data
    restart: unless-stopped

volumes:
  thule-data:
```

## Features

- **Card Grid** — customizable cards with icons, URLs, and sizes (1×1, 2×1, 1×2, 2×2)
- **Open Mode** — per-card choice to open the link in a new tab or the same tab
- **Drag-and-Drop** — reorder cards via drag & drop
- **Search** — built-in search bar with autocomplete (Google, DuckDuckGo, Bing, Yandex)
- **Background Images** — upload with drag-and-drop, blur control
- **Light/Dark Theme** — toggle with persistence
- **Import/Export** — backup all data to JSON
- **Auto Favicon** — automatic icon fetching from websites (with SSRF protection)
- **Asset Caching** — icons & static assets served with `Cache-Control` (no more re-downloading icons on every load)
- **Responsive** — desktop, tablet, and mobile support

## Architecture

| Component | Technology |
|-----------|------------|
| Backend | FastAPI + uvicorn + SQLite |
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

## Health Check

```
GET http://localhost:8000/api/health
```

Response: `{"status": "healthy", "version": "1.0.0"}`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/settings` | Get settings |
| `PUT` | `/api/settings` | Update settings |
| `GET` | `/api/cards` | Get all cards |
| `POST` | `/api/cards` | Create card |
| `PUT` | `/api/cards/{id}` | Update card |
| `DELETE` | `/api/cards/{id}` | Delete card |
| `POST` | `/api/cards/reorder` | Reorder cards |
| `GET` | `/api/full-data` | Get settings + cards |
| `POST` | `/api/upload` | Upload image |
| `POST` | `/api/fetch-icon` | Fetch favicon from URL |

## Tags

| Tag | Description |
|-----|-------------|
| `latest` | Latest stable build |
| `1.1.0` | Per-card open mode, asset caching, frontend stability fixes |
| `1.0.0` | Initial release |

## Source Code

[GitHub — Nezhirn/thule-homepage](https://github.com/Nezhirn/thule-homepage)

## License

MIT
