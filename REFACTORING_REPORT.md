# Итоговый отчёт о рефакторинге thule-homepage

**Дата:** 2026-09-10 · **Коммиты:** `1c4d1c9` (код), `3f4f0aa` (этот отчёт и `CODE_REVIEW.md`) · **Версия приложения:** 1.2.1
**Образ:** `thuleseeker/thule:latest` = `thuleseeker/thule:1.2.1` (`sha256:881eb235e72b57fa3bd5b2594c05d73e61b00dd964bf8798609a0f05fb4f87d8`)
**Объём:** 48 файлов, +5486/−1156 (код); +931 (документация в `3f4f0aa`)

Работа выполнена по `CODE_REVIEW.md` (7 Critical, 22 High, 40 Medium, ~40 Low).
Каждая находка проверена по коду; несогласные рекомендации отклонены с обоснованием (см. §4).

---

## 1. Резюме

- Закрыты Critical и High: удалён открытый CORS, добавлена аутентификация, устранены
  произвольное удаление файлов, потеря обоев/иконок при частичном обновлении, SSRF, stored XSS
  и разрушительный импорт. Аутентификация опциональна, поэтому **C1 закрыт условно** (см. §3, §7).
- Данные теперь защищены единым invariant: файлы удаляются только после успешного commit БД и
  только если на них никто не ссылается; миграции транзакционные и восстанавливаются после сбоя.
- Появился тестовый контур: **80 backend-тестов** (pytest) и **26 frontend-тестов** (vitest + jsdom),
  линтер ruff и CI (GitHub Actions, multi-arch build).
- Инфраструктура приведена к безопасному дефолту: контейнер от непривилегированного пользователя,
  порт на loopback, bind-mount `./homepage-data`, pinned-зависимости.
- Отдельно по обратной связи исправлен drag & drop: pointer capture, стабильный ghost без
  масштабирования, подсветка цели без перезапуска анимации каждый кадр, запрет нативного drag иконок.

---

## 2. Что сделано по группам

### 2.1 Безопасность периметра и API

| Что | Где |
|-----|-----|
| `CORSMiddleware` удалён полностью | `backend/main.py` |
| Опциональная токен-аутентификация `AUTH_TOKEN`: header `X-Auth-Token`/`Bearer` на все `/api/*` кроме `GET /api/health`; HttpOnly+SameSite=Strict cookie для `<img>`; мутации только по header | `backend/auth.py` |
| Security-заголовки: CSP, `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`; middleware зарегистрирован внешним, поэтому заголовки есть и на ранних 401 | `backend/main.py`, `tests/test_auth.py` |
| Rate limit 20/мин на `POST /api/fetch-icon` | `backend/ratelimit.py` |
| Порт по умолчанию привязан к `127.0.0.1` | `docker-compose.yml`, README |

### 2.2 Файлы, пути и целостность данных

| Что | Где |
|-----|-----|
| Единый `safe_upload_path()`: realpath/commonpath, запрет `..`, `\`, абсолютных путей и symlink-побегов; применён во всех точках склейки | `backend/services.py`, все routes |
| `background_image` валидируется как локальное имя; `icon_path` — http(s) URL или безопасное имя | `backend/services.py`, `schemas.py` |
| Частичное обновление через `model_fields_set`: «не передано» ≠ `null` (общий `apply_settings_patch`) | `backend/services.py`, `settings.py`, `data.py` |
| Удаление файлов только после commit и только при отсутствии ссылок (`upload_file_is_referenced`) | `services.py`, `cards.py`, `settings.py`, `data.py`, `uploads.py` |
| Импорт: валидация всех карточек до изменений → транзакция → commit → удаление осиротевших файлов; `HTTPException` не превращается в 500; логирование сбоя | `backend/routes/data.py` |
| Загрузки: тип по магическим байтам (content-type клиента игнорируется), SVG запрещён, лимит 10 МБ потоково, атомарная запись | `services.py`, `routes/uploads.py` |
| URL: allowlist `http/https/mailto` после вырезания control-символов | `services.py` |
| SSRF: fail-closed проверка всех DNS-адресов, allowlist схем, проверка каждого редиректа, лимиты 1 МБ/2 МБ, общий таймаут | `services.py` |

### 2.3 База данных

- WAL + `busy_timeout=30s` + `timeout=30` + `synchronous=NORMAL` (`database.py`).
- Транзакционные идемпотентные миграции; `PRAGMA user_version` выставляется как метка текущей
  ревизии (`SCHEMA_VERSION`), но чтением версии шаги не гейтятся — они идемпотентно выполняются при
  каждом старте. Это сознательный выбор: идемпотентный прогон надёжнее забытого bump'а версии.
  Восстановление прерванного rebuild (`cards_new`) без потери данных.
- Singleton `settings`: `CHECK (id = 1)` для новых БД, нормализация дублей, `INSERT OR IGNORE`,
  все чтения/записи — `WHERE id = 1`.
- `reorder` требует полный список ID без дубликатов; `position` пересчитывается на всех путях.
- `makedirs` для каталога БД до `init_db`.

### 2.4 Frontend

- Состояние модалки карточки вынесено в `this._modalState` — правка карточки больше не теряет
  иконку и размер (C6).
- Drag & drop переписан: Pointer Events + `setPointerCapture`, `pointercancel`,
  `touch-action: none` в edit-mode, long-press на тач, ghost через `translate3d` (без layout и
  scale), подсветка цели переключается только при смене цели, запрет нативного drag изображений.
- Планировщик перемещений делает честный swap (виртуальная занятость), не выходит за последнюю
  колонку; `_autoSpreadCards` учитывает размеры карточек.
- `api.js`: таймаут 10 с через AbortController, корректный разбор не-JSON ошибок и `detail`-массивов,
  заголовок токена.
- Безопасный рендеринг: подсказки поиска собираются DOM-узлами (XSS через атрибут закрыт), фон
  экранируется; карточки — настоящие `<a href>` (клавиатура, middle-click).
- Error-state с Retry; модалки с `role="dialog"`, focus trap и возвратом фокуса; тост `aria-live`;
  тема с откатом при ошибке записи; debounce сохранения blur.
- Ассеты версионируются автоматически (`?v=APP_VERSION`), `index.html` подставляет версию на сервере,
  поэтому обновление фронтенда не залипает в кеше браузера.

### 2.5 Инфраструктура

- Docker: non-root `uid 10001`, `HEALTHCHECK` удалён по требованию, `PORT` реально работает через
  `sh -c exec`, `APP_VERSION` из build-arg.
- `docker-compose.yml` / `docker-compose.prod.yml`: без `build`, без лимитов производительности,
  bind-mount `./homepage-data:/app/data`, ротация логов.
- `.dockerignore`: `**/*.db`, `**/uploads/`, `**/__pycache__`, node_modules — личные данные не
  попадают в образ (проверено сборкой).
- Точные пины зависимостей, `requirements-dev.txt`, `pyproject.toml` (ruff/pytest), CI с ruff,
  pytest, vitest, `pip-audit` и multi-arch сборкой.

### 2.6 Документация

- README и `DOCKER_HUB_DESCRIPTION.md` приведены к фактическому поведению: loopback, `AUTH_TOKEN`,
  bind-mount и права, backup через `sqlite3 .backup()`, реальные брейкпоинты, `/api/import`.
- Лицензия согласована: файл `LICENSE` — GPL-3.0, и бейдж с разделом в README/Docker Hub теперь тоже
  GPL-3.0.

---

## 3. Critical / High: статусы

| ID | Статус | Решение | Проверка |
|----|--------|---------|----------|
| C1 | FIXED (условно) | CORS удалён; auth-слой опционален (`AUTH_TOKEN` не задан → API открыт), дефолтный биндинг — loopback | `tests/test_auth.py` (8); контейнер: 401 без токена / 200 с токеном |
| C2 | FIXED | `safe_upload_path()` + валидатор background | `test_settings.py`, `test_uploads.py`; в контейнере `PUT /api/settings` c `/etc/passwd` → 400 |
| C3 | FIXED | `model_fields_set` + `apply_settings_patch` | `test_partial_update_preserves_background_image`, `test_explicit_null_clears...` |
| C4 | FIXED | Проверка каждого редиректа, лимиты, fail-closed | `tests/test_ssrf.py` (9 тестов) |
| C5 | FIXED | Allowlist схем + вырезание control-символов + клиентский `safeUrl` | `test_cards.py`, `components.test.js` |
| C6 | FIXED | `this._modalState` | `app-modal-state.test.js` (5 тестов) |
| C7 | FIXED | commit → orphan-diff с проверкой ссылок | `test_import_export.py` (12 тестов) |
| H1 | FIXED | SVG убран из upload и serve | `test_upload_rejects_svg_even_with_spoofed_content_type` |
| H2 | FIXED | Детект по магическим байтам | `test_upload_rejects_arbitrary_bytes` |
| H3 | FIXED | Потоковое чтение с обрывом | `test_upload_rejects_oversized_file` (413) |
| H4 | FIXED | Стриминг + лимиты + общий таймаут | `test_fetch_favicon_skips_oversized_icon`, `_fetch_limited_aborts_oversized_stream` |
| H5 | FIXED | WAL + busy_timeout; README про один worker | `database.py`, `README.md` |
| H6 | FIXED | Транзакции + recovery (идемпотентно, без гейта по версии) | `tests/test_database.py` (6 тестов) |
| H7 | FIXED | README/volume приведены к `/app/data` | `README.md`, compose |
| H8 | FIXED | `USER app`, uid 10001 | `docker exec id` → `uid=10001(app)` |
| H9 | FIXED | `.dockerignore` | build: COPY `backend/homepage.db` → «excluded by .dockerignore» |
| H10 | FIXED | `except HTTPException: rollback; raise` + logger | `test_import_rollback_keeps_cards_and_files_on_invalid_input` |
| H11 | FIXED | `logger.warning(..., exc_info=True)`, без `except: pass` | ruff чист |
| H12 | FIXED | DOM-рендер подсказок | `components.test.js::renderSuggestions` |
| H13 | FIXED | `text()` → try JSON, статус сохраняется | `api.test.js` (6 тестов) |
| H14 | FIXED | AbortController + таймаут 10 с | `api.test.js` |
| H15 | FIXED | Error-state + Retry | `components.js::renderErrorState` |
| H16 | FIXED | Карточки — `<a href>` | `components.test.js` |
| H17 | FIXED | Singleton settings | `test_settings_singleton_is_normalised` |
| H18 | FIXED | Sync-маршруты в threadpool, async только для async I/O | `backend/routes/*` |
| H19 | FIXED | Полный набор ID без дублей | `test_reorder_requires_complete_unique_set` |
| H20 | FIXED | Сброс inline-позиций на 1024px | `styles.css` |
| H21 | FIXED | 80 pytest + 26 vitest, ruff, CI, пины | см. §5 |
| H22 | FIXED | README/Docker Hub — GPL-3.0 | доки |

---

## 4. Medium / Low

**Исправлено полностью:** M1, M3, M4, M6–M12, M16–M25, M30, M32, M35–M40; удалён мёртвый код
(`models.py`, неиспользуемые импорты/методы, `#card-id`, `data-url`, дубли CSS-переменных).

**Решено иначе, чем рекомендовало ревью (рабочая альтернатива):**

| ID | Что сделано | Почему так |
|----|-------------|------------|
| M13 | Колонка `position` оставлена, но зеркалируется через `position_for()` на create/update/reorder/import | Удаление колонки — миграция данных ради косметики; рассинхрона больше нет |
| M14 | Backend — единый `config.COLS_PER_ROW`; фронтенд определяет число колонок из computed CSS | Литерал `7` остался только начальным fallback (`app.js:19`, `components.js:140`), но всегда перезаписывается `_detectGridCols()`; API `cols` не понадобился |

**Изменено по явному требованию заказчика (осознанное расхождение с ревью):**

| ID | Состояние | Комментарий |
|----|-----------|-------------|
| M27 | `docker-compose.prod.yml` восстановлен, но без `mem_limit`/`cpus` | Лимиты убраны по запросу (§2.5) |
| M28 | Секция `build:` из обоих compose удалена | Сборка — отдельной командой `docker build`; README поправлен |
| M29 | `HEALTHCHECK` из Dockerfile удалён | Эндпоинт `/api/health` сохранён, healthcheck не нужен |
| M31 | `mem_limit`/`cpus`/`pids_limit` убраны, ротация логов оставлена | Лимиты убраны по запросу; лог-ротация — не лимит производительности |

**Осознанно оставлено (риск/фича):**

| ID | Причина |
|----|---------|
| M2 | DNS rebinding: нужен pinning IP в транспорт httpx — отдельная задача, риск задокументирован |
| M5 | Внешние `icon_path` — заявленная фича (поле «Icon URL»); схемы провалидированы, трекинг-риск описан |
| M15 | `POST /api/cards/reorder` оставлен как публичный API (покрыт тестами); мёртвый JS-клиент удалён |
| M26 | Google Fonts / Wikipedia / внешние иконки — задокументированный остаточный риск |
| M33 | Точные пины + `pip-audit` в CI; хэши зависимостей не добавлены |
| M34 | Бейдж Python 3.12+ соответствует образу; digest базового образа не пинован |
| L2 | Переименование `/api/upload` сломало бы совместимость |
| L22/L27 | Оставшиеся `!important` и CSS-дубли — визуальный риск без функциональной выгоды |

---

## 5. Верификация (фактические запуски)

| Команда | Результат |
|---------|-----------|
| `ruff check backend tests` | `All checks passed!` |
| `pytest` | `80 passed` |
| `npm test` (vitest + jsdom) | `Tests 26 passed` |
| `pip-audit -r backend/requirements.txt` | `No known vulnerabilities found` |
| `docker build` | `Successfully built` |
| Smoke контейнера | `/api/health` → `{"status":"healthy","version":"1.2.1"}`, `/` → 200, `PUT /api/settings {"background_image":"/etc/passwd"}` → 400, `docker exec id` → `uid=10001(app)` |
| Auth-смоук | без токена `/api/full-data` → 401 (с `nosniff`/`DENY` в ответе), `GET /api/health` → 200, с `X-Auth-Token` → 200 |
| Разбивка pytest | auth 8 · cards 16 · database 6 · health 6 · import/export 12 · settings 8 · ssrf 9 · uploads 15 = **80** |
| Разбивка vitest | api 6 · app-modal-state 5 · components 7 · drag 8 = **26** |
| `.dockerignore` | COPY `backend/homepage.db` → «excluded by .dockerignore»; COPY `frontend/index.html` → успех |
| `docker compose config --quiet` | OK |
| Bind-mount | данные перенесены из `thule-homepage_thule-data` в `./homepage-data`, карточки и иконка на месте |

Покрытие тестами: path traversal/абсолютные пути/symlink, схемы и control-символы, SSRF
(редиректы/private IP/oversized), SVG/spoofed content-type/лимит, partial update/null,
сохранение icon/size при update, rollback импорта, round-trip иконок, миграции/recovery/singleton,
auth, API-ошибки/таймаут, modal state, XSS подсказок/CSS, drag & drop (swap, границы, padding,
spread, ghost+persist, native drag prevention).

---

## 6. Деплой и git

- Образ собран и опубликован: `thuleseeker/thule:latest` и `thuleseeker/thule:1.2.1` (один digest).
- `docker-compose.yml` запускает сервис на `http://localhost:8000` с bind-mount `./homepage-data`.
- Коммит `1c4d1c9` (код) и `3f4f0aa` (этот отчёт + `CODE_REVIEW.md`), запушены в `origin/main`
  (`e590caa..3f4f0aa`). Пуш выполнен по SSH: HTTPS-remote без сохранённых креденшелов.

---

## 7. Остаточные риски и ограничения

1. **Аутентификация опциональна**: при `AUTH_TOKEN` не заданном инсталляция, открытая в сеть, не
   защищена. По умолчанию порт слушает loopback; для сетевого доступа обязательно задать токен.
2. **DNS rebinding** (M2) и сторонние сервисы фронтенда (M26) — см. §4.
3. **CSP `img-src https:`** допускает загрузку внешних картинок; при появлении нового XSS это канал
   эксфильтрации. Все известные векторы XSS закрыты.
4. **Rate limiter в памяти** — на процесс; при нескольких воркерах лимит мягче.
5. **Визуальная проверка** вёрстки (769–1024px) и полный a11y-аудит в скринридере не проводились.
6. **Многоархитектурная сборка** описана в CI, локально собран только amd64. **Python 3.12**
   проверен локально; заявленная совместимость кода с 3.10 прогоном не подтверждена.
7. Дашборды/метрики и hot-reload для разработки сознательно не добавлялись.

---

## 8. Артефакты

| Артефакт | Назначение |
|----------|------------|
| `backend/config.py` | единая конфигурация (пути, лимиты, версия) |
| `backend/auth.py` | токен-аутентификация |
| `backend/ratelimit.py` | лимит на fetch-icon |
| `docker-compose.yml`, `docker-compose.prod.yml` | запуск с bind-mount |
| `pyproject.toml`, `requirements-dev.txt`, `vitest.config.js`, `package.json` | линт и тесты |
| `tests/` | 80 backend + 26 frontend тестов |
| `.github/workflows/ci.yml` | CI: ruff, pytest, vitest, pip-audit, multi-arch build |
| `README.md`, `DOCKER_HUB_DESCRIPTION.md` | актуальная документация и деплой |
| `CODE_REVIEW.md` | исходное ревью (коммит `3f4f0aa`) |
| `REFACTORING_REPORT.md` | этот отчёт (коммит `3f4f0aa`) |
