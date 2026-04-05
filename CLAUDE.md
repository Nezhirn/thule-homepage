# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A personal homepage / start page application with a Gnome 42-inspired aesthetic. Customizable card-based grid with search, editable links, background images, and themes — essentially a "new tab" replacement dashboard.

**Tech stack**: Python FastAPI backend with SQLite (raw `sqlite3`, not SQLAlchemy), vanilla HTML/CSS/JS frontend (no build tooling, no framework).

## Key Commands

- **Install dependencies**: `cd backend && pip install -r requirements.txt`
- **Run dev server**: `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
- **Run frontend directly**: Open `frontend/index.html` in a browser, or access via `http://localhost:8000/` (served by FastAPI)

There is no build step, linter, or test framework. The frontend is plain HTML/CSS/JS served as static files.

## Architecture

### Backend (`backend/`)

- `main.py` — FastAPI app, all routes, Pydantic schemas, and business logic in a single file. Static files (`/css`, `/js`, `index.html`) are mounted and served from the same port. Serves both the API and frontend.
- `database.py` — SQLite setup with connection-per-request pattern and schema migration logic.
- `models.py` and `schemas.py` — Stub/placeholder files. Actual models are in `main.py`.

**Key API endpoints**: `/api/cards` (CRUD + reorder), `/api/settings` (get/update), `/api/full-data` (settings + cards combined), `/api/upload`+`/api/uploads/` (file management), `/api/fetch-icon` (favicon fetching), `/api/health`.

**Database**: Two tables — `settings` (single row with background_image, blur_radius, dark_mode) and `cards` (id, title, url, icon_path, size, position).

### Frontend (`frontend/`)

Three-layer separation, all exposed as globals on `window`:

1. **`js/api.js`** → `window.api` — `ApiClient` class wrapping `fetch` with JSON serialization and per-endpoint methods.
2. **`js/components.js`** → `window.Components` — Pure DOM rendering functions (card elements, modals, toasts, theme toggle, background updates, file upload with drag-and-drop).
3. **`js/app.js`** → `window.App` — `HomepageApp` class orchestrating state and event handlers. Handles search (with autocomplete, configurable engines), card CRUD modal, drag-and-drop reordering (mouse-based, edit mode only), and JSON import/export.

**CSS**: Custom properties for light/dark theming, CSS Grid with `auto-fill` for responsive layout, card sizes (`1x1`, `2x1`, `1x2`, `2x2`) via grid spans. Edit mode toggled via `body.edit-mode` class.

**Bundled fallback**: `backend/frontend_index.html` and `dist/index.html` are self-contained monolithic copies with all CSS/JS inlined.

## Conventions

- Pydantic schemas defined inline in `main.py`, not in separate files.
- Each API endpoint opens and closes its own `sqlite3` connection.
- No ES modules — all frontend scripts loaded with `<script>` tags, using IIFE/class pattern with `window` globals.
- Uploaded files use UUID hex names to avoid collisions.
- URL validation blocks `javascript:`, `data:`, and `vbscript:` schemes. File serving blocks path traversal.
- See `SPEC.md` for the full project specification.
