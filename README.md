# Homepage — Персональная стартовая страница

![Описание картинки](https://lh3.googleusercontent.com/d/1mY7msiW8Zi9PQux-jC-hxruk8b1u-WlD)
**Настраиваемая домашняя страница с карточной сеткой, поиском, фоновыми изображениями и эстетикой Gnome 42.**

![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)
![License](https://img.shields.io/badge/License-GPLv3-blue.svg)

## Возможности

- **Карточная сетка** — настраиваемые карточки с иконками, URL и размерами (1×1, 2×1, 1×2, 2×2)
- **Режим открытия ссылки** — для каждой карточки выбирается, открывать URL в новой или в текущей вкладке
- **Drag-and-drop** — перетаскивание карточек для изменения порядка (режим редактирования), конфликты позиций разрешаются одним пакетом запросов
- **Поиск** — встроенная строка поиска с автодополнением (Google, DuckDuckGo, Bing, Yandex)
- **Фоновые изображения** — загрузка с drag-and-drop и настройкой размытия
- **Светлая/тёмная тема** — переключение с сохранением настроек
- **Импорт/экспорт** — резервное копирование всех данных в JSON (транзакционный импорт)
- **Авто-фавиконки** — автоматическое получение иконок сайтов с SSRF-защитой
- **Кэширование статики** — иконки и ассеты отдаются с `Cache-Control`
- **Адаптивность** — поддержка десктопа, планшета и мобильных устройств
- **Безопасность** — опциональная токен-аутентификация, allowlist схем URL, валидация загружаемых файлов по сигнатуре, безопасная работа с путями

## Быстрый старт

### Docker (рекомендуемый способ)

```bash
docker run -d -p 127.0.0.1:8000:8000 -v thule-data:/app/data thuleseeker/thule:latest
```

Откройте [http://localhost:8000](http://localhost:8000).

Порт привязывается к `127.0.0.1`: приложению не нужен сетевой периметр, а учётных записей у него нет. Для доступа из локальной сети или из интернета **обязательно** задайте `AUTH_TOKEN` и поставьте приложение за reverse proxy с TLS (см. «Безопасность»).

Том `thule-data` хранит БД и загруженные файлы (`/app/data`). Именованный том сохраняет владельца-пользователя контейнера (`uid 10001`). Если используете bind-mount (`-v ./homepage-data:/app/data`), каталог на хосте должен принадлежать `10001:10001`, иначе контейнер не сможет писать.

### Docker Compose

**Development** (сборка локального образа):

```bash
docker compose up -d --build
```

**Production** (опубликованный образ, лимиты ресурсов и ротация логов):

```bash
docker compose -f docker-compose.prod.yml up -d
```

### Ручная установка

```bash
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --host 127.0.0.1 --port 8000
```

Для зависимостей разработки (pytest, ruff): `pip install -r requirements-dev.txt`.

## Конфигурация

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `PORT` | `8000` | Порт, который слушает uvicorn в Docker-образе |
| `DATABASE_PATH` | `backend/homepage.db` | Путь к файлу SQLite |
| `UPLOADS_DIR` | `backend/uploads` | Каталог загруженных изображений |
| `AUTH_TOKEN` | — | Если задан, включает токен-аутентификацию API |
| `APP_VERSION` | `1.2.1` | Версия, которую отдаёт `/api/health` |
| `LOG_LEVEL` | `INFO` | Уровень логирования |

### Аутентификация

Аутентификация включается переменной `AUTH_TOKEN` и по умолчанию выключена (рассчитана на `127.0.0.1`). Когда токен задан:

- все `/api/*`, кроме `GET /api/health`, требуют заголовок `X-Auth-Token: <токен>` или `Authorization: Bearer <токен>`;
- браузер после первого успешного запроса получает HttpOnly cookie `thule_session`, чтобы `<img src="/api/uploads/...">` работали без заголовков; cookie `SameSite=Strict`;
- веб-интерфейс показывает окно ввода токена и хранит его в `localStorage` браузера;
- токен никогда не попадает в отдаваемый HTML, поэтому сканирование порта без токена не даёт доступа.

```bash
docker run -d -p 127.0.0.1:8000:8000 \
  -e AUTH_TOKEN="$(openssl rand -hex 32)" \
  -v thule-data:/app/data thuleseeker/thule:latest
```

## Архитектура

```
homepage/
├── backend/
│   ├── main.py           # FastAPI-приложение, middleware (auth, security headers, cache)
│   ├── config.py         # Конфигурация из env (пути, лимиты, версия)
│   ├── auth.py           # Опциональная токен-аутентификация
│   ├── database.py       # SQLite: подключение, WAL, транзакционные миграции
│   ├── schemas.py        # Pydantic-схемы запросов/ответов
│   ├── services.py       # Валидация, безопасные пути, SSRF-защита, файлы
│   ├── ratelimit.py      # Лимит запросов на /api/fetch-icon
│   ├── routes/           # Маршруты: settings, cards, uploads, favicon, data
│   └── requirements.txt  # Python-зависимости (запинены)
├── frontend/
│   ├── index.html        # HTML-разметка
│   ├── css/styles.css    # Все стили
│   └── js/
│       ├── theme-init.js # Применение темы до первой отрисовки
│       ├── api.js        # API-клиент (fetch wrapper с таймаутом)
│       ├── components.js # Рендеринг UI (карточки-ссылки, модалки, тосты)
│       └── app.js        # Главный класс приложения, обработчики событий
├── tests/                # pytest (backend) и vitest (frontend)
└── README.md
```

### Фронтенд

| Файл | Глобальный объект | Назначение |
|------|-------------------|------------|
| `js/api.js` | `window.api` | HTTP-клиент: таймаут 10 с, разбор ошибок, заголовок токена |
| `js/components.js` | `window.Components` | DOM-рендеринг, темы, модалки, загрузка файлов |
| `js/app.js` | `window.App` | Класс `HomepageApp` — состояние и обработчики |

Карточки-ссылки рендерятся как настоящие `<a href>` (клавиатура, средняя кнопка, «открыть в новой вкладке»). В режиме редактирования используется `<div>`.

### Бэкенд

- **FastAPI** + **uvicorn**; синхронные SQLite-маршруты выполняются в threadpool
- **SQLite** (raw `sqlite3`, без ORM) в режиме WAL с `busy_timeout = 30s`
- **Соединение на запрос**, транзакция на мутацию; файлы удаляются только после успешного commit
- **Pydantic** — валидация (ограничение длин, диапазонов, запрет неизвестных полей)
- **Загрузка файлов** — тип определяется по магическим байтам, UUID-имена, лимит 10 МБ с потоковым чтением
- **HTTP-кэширование** — иконки/загрузки `immutable` на год, `/css` и `/js` — `no-cache` с ревалидацией (файлы без хэшей), `index.html` — `no-cache`

## API Reference

### Settings

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/settings` | Получить настройки |
| `PUT` | `/api/settings` | Частичное обновление (`background_image`, `blur_radius`, `dark_mode`) |

`PUT` различает «поле не передано» (не трогать) и `null` (очистить). `background_image` принимает только имя локального файла из `uploads/`.

### Upload

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/upload` | Загрузить изображение (JPEG, PNG, GIF, WebP; до 10 МБ) |
| `GET` | `/api/uploads/{filename}` | Получить файл (`Cache-Control: immutable`) |
| `DELETE` | `/api/upload/{filename}` | Удалить файл; 409, если на него ссылаются карточка или фон |

### Favicon

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/fetch-icon` | Получить фавиконку URL (SSRF-защита, лимит 20 запросов/мин на IP) |

### Cards

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/cards` | Все карточки (сортировка по `grid_row`, `grid_col`) |
| `POST` | `/api/cards` | Создать карточку (авто-размещение с учётом размера) |
| `PUT` | `/api/cards/{card_id}` | Частичное обновление; `url`/`icon_path` можно очистить через `null` |
| `DELETE` | `/api/cards/{card_id}` | Удалить карточку (204) |
| `POST` | `/api/cards/reorder` | Переупорядочить карточки; требует полный список ID без дубликатов |

### Прочее

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/full-data` | Настройки + карточки за один запрос |
| `POST` | `/api/import` | Транзакционный импорт настроек и карточек (полностью деструктивный) |
| `GET` | `/api/health` | Health check (`{"status": "healthy", "version": "1.2.1"}`) |
| `GET` | `/` | Отдаёт `index.html` |

## База данных

### Таблица `settings` (одна строка, `id = 1`)

| Столбец | Тип | По умолчанию |
|---------|-----|--------------|
| `id` | INTEGER PK | 1 (CHECK) |
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
| `position` | INTEGER | 0 (производное от `grid_col`/`grid_row`) |
| `grid_col` | INTEGER | 1 |
| `grid_row` | INTEGER | 1 |
| `open_in_new_tab` | INTEGER | 1 |

Индекс: `idx_cards_grid (grid_row, grid_col)`.

Миграции версионируются (`PRAGMA user_version`) и выполняются в одной транзакции: прерывание не оставляет схему в половинчатом состоянии. Поддерживаются старые схемы (`icon_data`, `tab_id`, `background_data`).

## Безопасность

Приложение рассчитано на одного пользователя и по умолчанию привязано к loopback. Аутентификация включается через `AUTH_TOKEN` и должна использоваться при любом сетевом доступе.

- **CORS отключён** — фронтенд отдаётся с того же origin; cross-origin чтение API невозможно
- **Аутентификация** — общий токен на все `/api/*` кроме health (см. выше)
- **SSRF** — allowlist `http`/`https`, проверка всех адресов DNS перед запросом (fail-closed), проверка каждого редиректа, лимит ответа 2 МБ
- **Валидация URL** — allowlist схем (`http`, `https`, `mailto`) после удаления control-символов (`java\tscript:` не проходит)
- **Path traversal** — `background_image` и `icon_path` принимаются только как локальные имена; единый `safe_upload_path()` с `realpath`/`commonpath` reject-ит абсолютные пути, `..` и symlink-побеги
- **Загружаемые файлы** — тип определяется по магическим байтам (content-type клиента не учитывается), SVG запрещён, лимит 10 МБ проверяется потоково
- **Целостность данных** — удаление файлов только после commit БД; импорт валидирует всё до изменения состояния; при сбое транзакция откатывается, файлы не теряются
- **Заголовки** — `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`

Остаточные риски: DNS rebinding (проверка DNS и подключение не привязаны к одному IP) и сторонние сервисы фронтенда (Google Fonts, подсказки Wikipedia, внешние иконки). Для приватных инсталляций их стоит заменить на локальные ресурсы.

## Бэкап и восстановление

Обычный `cp` файла SQLite во время записи может дать повреждённую копию. Используйте горячий бэкап:

```bash
# 1. Консистентная копия БД внутри контейнера
docker exec thule-homepage python -c "\
import sqlite3; src=sqlite3.connect('/app/data/homepage.db'); \
dst=sqlite3.connect('/app/data/backup.db'); src.backup(dst); dst.close(); src.close()"

# 2. БД + загруженные файлы (данные лежат в ./homepage-data)
cp homepage-data/backup.db .
cp -r homepage-data/uploads ./uploads-backup
```

Также доступен `Export Data` в настройках — JSON со всеми карточками. Импорт (`Import Data` или `POST /api/import`) полностью заменяет карточки и настройки; валидация выполняется до изменений, а файлы, на которые ссылаются новые карточки, сохраняются.

## Разработка

```bash
pip install -r requirements-dev.txt
ruff check backend tests
pytest                       # 77 backend-тестов
npm install
npm test                     # 18 frontend-тестов (vitest + jsdom)
docker build --network=host -t thule-homepage .
```

## Конвенции разработки

### Бэкенд
- Pydantic-схемы — в `schemas.py`, бизнес-логика — в `services.py`, маршруты — в `routes/`
- Каждый endpoint открывает и закрывает своё `sqlite3`-подключение; мутации — в транзакции
- Файлы удаляются только после успешного commit, только через `delete_upload_file()`
- Загруженные файлы получают UUID-имена; путь всегда строится через `safe_upload_path()`
- Миграции базы — в `database.py`, транзакционные и идемпотентные

### Фронтенд
- Без ES-модулей — классические `<script>` с `defer`, глобальные `window`-объекты
- Состояние модалки карточки — в `this._modalState`, а не в замыканиях
- Ссылки-карточки — реальные `<a>`, в edit-mode — `<div>`
- CSS Grid с явными `grid-column`/`grid-row` на десктопе; на мобильных позиции сбрасываются

## Адаптивные брейкпоинты

| Ширина экрана | Колонок |
|---------------|---------|
| > 1024px | 7 |
| 769–1024px | 4 |
| 481–768px | 3 |
| 381–480px | 2 |
| ≤ 380px | 1 |

## Развёртывание

### Production Docker Compose

```bash
docker compose -f docker-compose.prod.yml up -d
```

Запускает контейнер на `127.0.0.1:8000` с bind-mount `./homepage-data` и ротацией логов.

### Однопроцессный режим

Запускайте **один** worker: приложение однопользовательское. SQLite работает в режиме WAL и переживает параллельные запросы, но `--workers 4` не даёт выигрыша и создаёт лишние писатели.

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

### Docker Hub

Образ: [thuleseeker/thule](https://hub.docker.com/r/thuleseeker/thule)

```bash
docker pull thuleseeker/thule:latest
```

Теги: `latest`, `1.2.1`.

## Лицензия

Проект распространяется под лицензией **GNU General Public License v3.0** — см. файл [LICENSE](LICENSE).
