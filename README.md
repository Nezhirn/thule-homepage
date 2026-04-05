# Homepage — Персональная стартовая страница

![Описание картинки](https://lh3.googleusercontent.com/d/1mY7msiW8Zi9PQux-jC-hxruk8b1u-WlD)
**Настраиваемая домашняя страница с карточной сеткой, поиском, фоновыми изображениями и эстетикой Gnome 42.**

![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)
![License](https://img.shields.io/badge/License-MIT-blue.svg)

## Возможности

- **Карточная сетка** — настраиваемые карточки с иконками, URL и размерами (1×1, 2×1, 1×2, 2×2)
- **Drag-and-drop** — перетаскивание карточек для изменения порядка (режим редактирования)
- **Поиск** — встроенная строка поиска с автодополнением (Google, DuckDuckGo, Bing, Yandex)
- **Фоновые изображения** — загрузка с drag-and-drop и настройкой размытия
- **Светлая/тёмная тема** — переключение с сохранением настроек
- **Импорт/экспорт** — резервное копирование всех данных в JSON
- **Авто-фавиконки** — автоматическое получение иконок сайтов через API
- **Адаптивность** — поддержка десктопа, планшета и мобильных устройств
- **Безопасность** — SSRF-защита, валидация URL, sanitization файлов

## Скриншоты

> *Здесь можно добавить скриншоты приложения*

## Быстрый старт

### Docker (рекомендуемый способ)

```bash
docker run -d -p 8000:8000 thuleseeker/thule:latest
```

Откройте [http://localhost:8000](http://localhost:8000).

Для сохранения данных между перезапусками используйте volume:

```bash
docker run -d -p 8000:8000 -v thule-data:/app/backend thuleseeker/thule:latest
```

#### Docker Compose

**Development:**

```bash
docker compose up -d --build
```

**Production:**

```bash
docker compose -f docker-compose.prod.yml up -d
```

### Ручная установка

#### 1. Установка зависимостей

```bash
cd backend
pip install -r requirements.txt
```

#### 2. Запуск сервера

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### 3. Открыть в браузере

Перейдите по адресу **[http://localhost:8000](http://localhost:8000)**

## Архитектура

```
homepage/
├── backend/
│   ├── main.py           # FastAPI-приложение, маршруты, схемы, бизнес-логика
│   ├── database.py       # SQLite: подключение и миграции
│   ├── requirements.txt  # Python-зависимости
│   ├── homepage.db       # База данных (gitignored)
│   └── uploads/          # Загруженные изображения (gitignored)
├── frontend/
│   ├── index.html        # HTML-разметка
│   ├── css/
│   │   └── styles.css    # Все стили (~1200 строк)
│   └── js/
│       ├── api.js        # API-клиент (fetch wrapper)
│       ├── components.js # Рендеринг UI (карточки, модалки, темы)
│       └── app.js        # Главный класс приложения, обработчики событий
└── README.md
```

### Фронтенд

Архитектура с тремя уровнями разделения (без ES-модулей, всё через `<script>`):

| Файл | Глобальный объект | Назначение |
|------|-------------------|------------|
| `js/api.js` | `window.api` | HTTP-клиент с обёрткой над `fetch` |
| `js/components.js` | `window.Components` | Функции DOM-рендеринга, тем, загрузка файлов |
| `js/app.js` | `window.App` | Класс `HomepageApp` — состояние и обработчики |

Состояние (тема, поисковик, режим редактирования) сохраняется в `localStorage`. Карточки хранятся только на сервере.

### Бэкенд

- **FastAPI** + **uvicorn** — сервер и маршрутизация
- **SQLite** (raw `sqlite3`, без ORM) — сырые SQL-запросы с `sqlite3.Row`
- **Соединение на запрос** — каждый endpoint открывает и закрывает своё подключение
- **Pydantic** — валидация и сериализация (схемы определены прямо в `main.py`)
- **Загрузка файлов** — UUID-имена для избежания коллизий, ограничение 10 МБ

## API Reference

### Settings

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/settings` | Получить все настройки пользователя |
| `PUT` | `/api/settings` | Обновить настройки (`background_image`, `blur_radius`, `dark_mode`) |

### Upload

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/upload` | Загрузить изображение |
| `GET` | `/api/uploads/{filename}` | Получить загруженное изображение |
| `DELETE` | `/api/upload/{filename}` | Удалить загруженное изображение |

### Favicon

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/fetch-icon` | Получить фавиконку с указанного URL (с SSRF-защитой) |

### Cards

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/cards` | Получить все карточки (сортировка по `grid_row`, `grid_col`) |
| `POST` | `/api/cards` | Создать карточку |
| `PUT` | `/api/cards/{card_id}` | Обновить карточку |
| `DELETE` | `/api/cards/{card_id}` | Удалить карточку |
| `POST` | `/api/cards/reorder` | Переупорядочить карточки (список ID) |

### Прочее

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/full-data` | Получить настройки + карточки за один запрос |
| `GET` | `/api/health` | Health check (`{"status": "healthy"}`) |
| `GET` | `/` | Сервит фронтенд (`index.html`) |

## База данных

### Таблица `settings` (одна строка)

| Столбец | Тип | По умолчанию |
|---------|-----|--------------|
| `id` | INTEGER PK | AUTOINCREMENT |
| `background_image` | TEXT | NULL |
| `blur_radius` | INTEGER | 0 |
| `dark_mode` | INTEGER | 0 |

### Таблица `cards`

| Столбец | Тип | По умолчанию |
|---------|-----|--------------|
| `id` | INTEGER PK | AUTOINCREMENT |
| `title` | TEXT | NOT NULL |
| `url` | TEXT | NULL |
| `icon_path` | TEXT | NULL |
| `size` | TEXT | `'1x1'` |
| `position` | INTEGER | 0 |
| `grid_col` | INTEGER | 1 |
| `grid_row` | INTEGER | 1 |

## Технологии

### Бэкенд

| Пакет | Назначение |
|-------|------------|
| `fastapi>=0.100.0` | Веб-фреймворк |
| `uvicorn>=0.23.0` | ASGI-сервер |
| `pydantic>=2.0.0` | Валидация данных |
| `python-multipart>=0.0.6` | Парсинг multipart-форм |
| `httpx>=0.25.0` | HTTP-клиент (для фавиконок) |

### Фронтенд

- **Vanilla JS** — без фреймворков и сборки
- **CSS Grid** — адаптивная сетка с `repeat(7, minmax(140px, 1fr))`
- **CSS Custom Properties** — темизация через `:root` / `[data-theme="dark"]`
- **Google Fonts** — шрифт Inter (400, 500, 600, 700)

## Безопасность

- **SSRF-защита** — фавиконки не запрашиваются с приватных/локальных IP
- **Валидация URL** — блокировка `javascript:`, `data:`, `vbscript:` схем
- **Path traversal** — блокировка `..`, `/`, `\` в именах файлов
- **Ограничение размера** — максимум 10 МБ на загружаемый файл
- **Разрешённые типы** — только JPEG, PNG, GIF, WebP, SVG
- **Пропуск SVG-фавиконок** — защита от XSS через `<script>` в SVG

## Конвенции разработки

### Бэкенд
- Pydantic-схемы определены inline в `main.py`
- Каждый endpoint открывает и закрывает своё `sqlite3` подключение
- Загруженные файлы получают UUID-имена (`uuid.uuid4().hex`)
- Миграции базы — в `database.py` (старые колонки `icon_data`, `tab_id`, `background_data`)

### Фронтенд
- Без ES-модулей — всё через `<script>` теги, IIFE + глобальные `window` объекты
- CSS Grid с явными `grid-column`/`grid-row` для карточек разных размеров
- Режим редактирования через `body.edit-mode` класс
- Drag-and-drop — мышиный (не HTML5 Drag and Drop API), привязан к grid-контейнеру

## Адаптивные брейкпоинты

| Ширина экрана | Колонок | Описание |
|---------------|---------|----------|
| > 1024px | 7 (default) | Полный десктоп |
| 768px — 1024px | 4 | Планшет |
| < 768px | 2 | Мобильный |

## Развёртывание

### Production Docker Compose

```bash
docker compose -f docker-compose.prod.yml up -d
```

Это запустит:
- Контейнер с приложением на порту `8000`
- Volume `thule-data` для хранения БД и загруженных файлов
- Health-check для мониторинга доступности
- Ограничение ресурсов (512MB RAM, 0.5 CPU)

```bash
docker compose -f docker-compose.prod.yml up -d
```

### Ручной запуск

```bash
# Запуск с uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Или через Gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Docker Hub

Образ доступен по адресу: [thuleseeker/thule](https://hub.docker.com/r/thuleseeker/thule)

```bash
docker pull thuleseeker/thule:latest
```

Теги: `latest`, `1.0.0`

## Лицензия

MIT
