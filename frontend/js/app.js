/**
 * Homepage Application
 */

/* Centralised search-engine configuration — single source of truth */
const SEARCH_ENGINES = {
    google:     { url: 'https://www.google.com/search?q=',     icon: 'https://www.google.com/favicon.ico' },
    duckduckgo: { url: 'https://duckduckgo.com/?q=',           icon: 'https://duckduckgo.com/favicon.ico' },
    bing:       { url: 'https://www.bing.com/search?q=',       icon: 'https://www.bing.com/s/a/bing.ico' },
    yandex:     { url: 'https://yandex.com/search/?text=',     icon: 'https://yandex.com/favicon.ico' },
};

class HomepageApp {
    constructor() {
        this.settings = null;
        this.cards = [];
        this.editingCard = null;
        this.editMode = false;
        this.gridCols = 7;

        // Search
        this.searchEngine = localStorage.getItem('searchEngine') || 'google';
        this.searchUrl = this._engineUrl(this.searchEngine);
        this.searchTimeout = null;

        // Card modal state (survives add/edit transitions)
        this._modalState = { size: '1x1', iconFile: null };

        // Drag & drop state (single shared instance)
        this._drag = {
            active: false, ghost: null, cursor: null, card: null,
            sx: 0, sy: 0, ox: 0, oy: 0,
            pointerId: null, metrics: null, cells: null, hoverKey: null,
        };

        this.init();
    }

    /* Detect grid columns from actual CSS computed style */
    _detectGridCols() {
        const grid = document.getElementById('cards-grid');
        if (!grid) return;
        const detected = getComputedStyle(grid).gridTemplateColumns.split(' ').length;
        if (detected > 0) this.gridCols = detected;
    }

    _engineUrl(engine) { return (SEARCH_ENGINES[engine] || SEARCH_ENGINES.google).url; }
    _engineIcon(engine) { return (SEARCH_ENGINES[engine] || SEARCH_ENGINES.google).icon; }

    async init() {
        Components.setTheme(localStorage.getItem('theme') || 'light');
        this.editMode = localStorage.getItem('editMode') === 'true';
        this._applyEditMode();
        this._updateEngineIcon();
        this._detectGridCols();
        this._setupModals();
        this._setupLogin();
        this._setupSearch();
        this._setupButtons();
        await this.loadData();
        this._initDragDrop();

        let resizeTimer;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => { this._detectGridCols(); this.renderCards(); }, 150);
        });
    }

    /* ==================== Edit mode ==================== */
    _applyEditMode() {
        document.body.classList.toggle('edit-mode', this.editMode);
        const btn = document.getElementById('edit-mode-btn');
        if (btn) {
            btn.classList.toggle('active', this.editMode);
            const s = btn.querySelector('span');
            if (s) s.textContent = this.editMode ? 'Done' : 'Edit';
        }
    }

    /* ==================== Drag & Drop (mouse+touch, snap-to-grid) ==================== */
    _initDragDrop() {
        const grid = document.getElementById('cards-grid');
        const d = this._drag;

        /* Build a lightweight clone used as the drag ghost. The menu and
         * dropdown are stripped, inline grid styles and animations removed so
         * the ghost only ever moves via a compositor-friendly transform. */
        const makeGhost = card => {
            const ghost = card.cloneNode(true);
            ghost.classList.add('drag-ghost');
            ghost.removeAttribute('data-id');
            ghost.removeAttribute('data-sig');
            ghost.setAttribute('aria-hidden', 'true');
            ghost.querySelectorAll('.card-menu-btn, .card-dropdown').forEach(el => el.remove());
            ghost.style.cssText = '';
            Object.assign(ghost.style, {
                position: 'fixed', margin: '0',
                opacity: '0.9', pointerEvents: 'none', zIndex: '9999',
                boxShadow: '0 16px 48px rgba(0,0,0,0.3)',
                transform: 'translate3d(0, 0, 0)',
                transition: 'none', animation: 'none', willChange: 'transform'
            });
            return ghost;
        };

        const beginDrag = (card, clientX, clientY, pointerId) => {
            if (d.active || !this.editMode) return;
            cancelPendingMove();
            const rect = card.getBoundingClientRect();
            const metrics = this._gridMetrics();

            d.active = true;
            d.pointerId = pointerId ?? null;
            d.card = card;
            d.sx = clientX; d.sy = clientY;
            d.ox = rect.left; d.oy = rect.top;
            d.metrics = metrics;
            d.targetCol = null; d.targetRow = null;
            d.hoverKey = null;
            d.cells = new Map();
            grid.querySelectorAll('.grid-cell').forEach(cell => {
                d.cells.set(`${cell.dataset.col},${cell.dataset.row}`, cell);
            });

            d.ghost = makeGhost(card);
            Object.assign(d.ghost.style, {
                left: rect.left + 'px', top: rect.top + 'px',
                width: rect.width + 'px', height: rect.height + 'px'
            });
            document.body.appendChild(d.ghost);
            card.classList.add('drag-source');

            if (d.pointerId != null && grid.setPointerCapture) {
                try { grid.setPointerCapture(d.pointerId); } catch (_) { /* ignore */ }
            }
        };

        /* rAF-throttled wrapper: collapse a burst of pointer moves into one
         * update per frame so heavy work (elementFromPoint + DOM scans) runs
         * at most ~60fps instead of on every mousemove/touchmove event. */
        const requestMove = (clientX, clientY) => {
            if (!d.active) return;
            d._lastX = clientX; d._lastY = clientY;
            if (d._rafId != null) return;
            d._rafId = requestAnimationFrame(() => {
                d._rafId = null;
                moveDrag(d._lastX, d._lastY);
            });
        };

        /* Drop any frame still queued — prevents a stale move from firing after
         * the drag ends (which would re-show the hidden ghost during endDrag's
         * await) or bleeding into the next drag with old coordinates. */
        const cancelPendingMove = () => {
            if (d._rafId != null) { cancelAnimationFrame(d._rafId); d._rafId = null; }
        };

        /* Update the drop highlight only when the target changes: re-adding the
         * class every frame restarts its CSS transition and makes it flicker. */
        const setHighlight = (col, row, targetCard) => {
            const key = targetCard ? `card:${targetCard.dataset.id}` : `cell:${col},${row}`;
            if (d.hoverKey === key) return;
            d.hoverKey = key;
            grid.querySelectorAll('.cell-highlight').forEach(c => c.classList.remove('cell-highlight'));
            grid.querySelectorAll('.card.drag-over').forEach(c => c.classList.remove('drag-over'));
            if (targetCard) {
                targetCard.classList.add('drag-over');
            } else if (d.cells) {
                d.cells.get(`${col},${row}`)?.classList.add('cell-highlight');
            }
        };

        const moveDrag = (clientX, clientY) => {
            if (!d.active || !d.ghost) return;
            /* Move via transform only — no layout/paint of left/top per frame,
             * no scaling: the ghost stays exactly the size of the card. */
            d.ghost.style.transform = `translate3d(${clientX - d.sx}px, ${clientY - d.sy}px, 0)`;

            /* The ghost has pointer-events: none, so it is never returned. */
            const el = document.elementFromPoint(clientX, clientY);
            const targetCell = el?.closest('.grid-cell');
            const targetCard = el?.closest('.card');

            if (targetCell) {
                d.targetCol = parseInt(targetCell.dataset.col);
                d.targetRow = parseInt(targetCell.dataset.row);
                setHighlight(d.targetCol, d.targetRow, null);
            } else if (targetCard && targetCard !== d.card) {
                const tid = parseInt(targetCard.dataset.id);
                const tc = this.cards.find(c => c.id === tid);
                d.targetCol = tc?.grid_col || 1;
                d.targetRow = tc?.grid_row || 1;
                setHighlight(d.targetCol, d.targetRow, targetCard);
            } else {
                const [col, row] = this._calcGridPos(clientX, clientY, d.metrics);
                d.targetCol = col; d.targetRow = row;
                setHighlight(col, row, null);
            }
        };

        const endDrag = async () => {
            if (!d.active) return;
            cancelPendingMove();

            /* Capture the drag state before awaiting: a new drag may start
             * while the network request is in flight. */
            const card = d.card;
            const targetCol = d.targetCol;
            const targetRow = d.targetRow;
            d.active = false;
            d.pointerId = null;
            d.card = null; d.targetCol = null; d.targetRow = null;
            this._cleanupDrag();
            if (card) card.classList.remove('drag-source');
            grid.querySelectorAll('.cell-highlight').forEach(c => c.classList.remove('cell-highlight'));
            grid.querySelectorAll('.card.drag-over').forEach(c => c.classList.remove('drag-over'));

            if (!card || targetCol === null || targetRow === null) return;

            const movedCardId = parseInt(card.dataset.id);
            const movedCard = this.cards.find(c => c.id === movedCardId);
            if (!movedCard) return;

            const moves = this._planMove(movedCard, targetCol, targetRow);
            if (!moves.length) return;

            try {
                await Promise.all(moves.map(m => api.updateCard(m.id, { grid_col: m.col, grid_row: m.row })));
                for (const move of moves) {
                    const c = this.cards.find(x => x.id === move.id);
                    if (c) { c.grid_col = move.col; c.grid_row = move.row; }
                }
                Components.showToast('Card moved to (' + targetCol + ',' + targetRow + ')');
            } catch (err) {
                Components.showToast('Failed to save move: ' + err.message, 'error');
                await this.loadCards();
            }
            this.renderCards();
        };

        /* Pointer events unify mouse, touch and pen. Pointer capture keeps
         * move/up events coming even when the cursor leaves the window, so a
         * drag can never get stuck half-finished. */
        let longPressTimer = null;
        let pendingTouch = null;

        const clearLongPress = () => {
            if (longPressTimer) { clearTimeout(longPressTimer); longPressTimer = null; }
            pendingTouch = null;
        };

        grid.addEventListener('pointerdown', e => {
            if (!this.editMode || (e.button !== undefined && e.button !== 0)) return;
            const card = e.target.closest('.card');
            if (!card) return;
            if (e.target.closest('.card-menu-btn') || e.target.closest('.card-dropdown')) return;
            e.preventDefault();

            if (e.pointerType === 'touch') {
                /* Long-press starts a drag; moving first means scrolling. */
                pendingTouch = { card, x: e.clientX, y: e.clientY, pointerId: e.pointerId };
                clearTimeout(longPressTimer);
                longPressTimer = setTimeout(() => {
                    longPressTimer = null;
                    if (pendingTouch) beginDrag(pendingTouch.card, pendingTouch.x, pendingTouch.y, pendingTouch.pointerId);
                    pendingTouch = null;
                }, 250);
            } else {
                beginDrag(card, e.clientX, e.clientY, e.pointerId);
            }
        });

        grid.addEventListener('pointermove', e => {
            if (pendingTouch) {
                if (Math.hypot(e.clientX - pendingTouch.x, e.clientY - pendingTouch.y) > 8) clearLongPress();
                return;
            }
            if (!d.active) return;
            if (d.pointerId != null && e.pointerId !== d.pointerId) return;
            requestMove(e.clientX, e.clientY);
        });

        const finishDrag = e => {
            clearLongPress();
            if (!d.active) return;
            if (e && d.pointerId != null && e.pointerId !== d.pointerId) return;
            endDrag();
        };
        grid.addEventListener('pointerup', finishDrag);
        grid.addEventListener('pointercancel', finishDrag);

        /* Never let the browser start its own drag on card images/links: a
         * native drag swallows pointer events and freezes the custom ghost. */
        grid.addEventListener('dragstart', e => {
            if (this.editMode && e.target.closest('.card')) e.preventDefault();
        });
        grid.addEventListener('contextmenu', e => {
            if (this.editMode && e.target.closest('.card')) e.preventDefault();
        });

        /* Fallbacks for cases where the pointer stream is interrupted. */
        window.addEventListener('blur', () => { clearLongPress(); endDrag(); });
        document.addEventListener('visibilitychange', () => { if (document.hidden) endDrag(); });
    }

    _cleanupDrag() {
        const d = this._drag;
        if (d.cursor) { d.cursor.remove(); d.cursor = null; }
        if (d.ghost) {
            if (d.ghost.parentNode) d.ghost.parentNode.removeChild(d.ghost);
            d.ghost = null;
        }
        d.metrics = null;
        d.cells = null;
        d.hoverKey = null;
    }

    /** Snapshot grid geometry once per drag; avoids getComputedStyle and
     *  getBoundingClientRect on every frame. */
    _gridMetrics() {
        const grid = document.getElementById('cards-grid');
        const gridRect = grid.getBoundingClientRect();
        const style = getComputedStyle(grid);
        const gap = parseFloat(style.gap) || 16;
        const paddingLeft = parseFloat(style.paddingLeft) || parseFloat(style.padding) || 0;
        const paddingTop = parseFloat(style.paddingTop) || parseFloat(style.padding) || 0;
        const cols = Math.max(1, style.gridTemplateColumns.split(' ').filter(Boolean).length);
        const cell = grid.querySelector('.grid-cell');
        const measuredCellH = cell ? cell.getBoundingClientRect().height : 0;
        const cellH = measuredCellH || parseFloat(style.gridAutoRows) || 160;
        const colWidth = (gridRect.width - paddingLeft * 2 - gap * (cols - 1)) / cols;
        return { gridRect, gap, paddingLeft, paddingTop, cellH, colWidth, cols };
    }

    /* Calculate grid column/row from absolute coordinates */
    _calcGridPos(mx, my, metrics) {
        const m = metrics || this._gridMetrics();
        this.gridCols = m.cols;
        const col = Math.floor((mx - m.gridRect.left - m.paddingLeft) / (m.colWidth + m.gap)) + 1;
        const row = Math.floor((my - m.gridRect.top - m.paddingTop) / (m.cellH + m.gap)) + 1;
        return [Math.max(1, Math.min(col, m.cols)), Math.max(1, row)];
    }

    /* ==================== Collision Resolution ==================== */

    /** Plan all card moves needed to drop movedCard at (newCol, newRow).
     *  Returns an array so the caller can persist them together. The conflict
     *  card is placed using a virtual occupancy that already includes the
     *  moved card at its target, so a swap can never leave two cards stacked. */
    _planMove(movedCard, newCol, newRow) {
        const [mw, mh] = (movedCard.size || '1x1').split('x').map(Number);
        const sizeOf = card => (card.size || '1x1').split('x').map(Number);

        const others = this.cards.filter(c => c.id !== movedCard.id);
        const owners = new Map();
        others.forEach(c => {
            const [cw, ch] = sizeOf(c);
            const gc = c.grid_col || 1, gr = c.grid_row || 1;
            for (let cc = gc; cc < gc + cw; cc++)
                for (let cr = gr; cr < gr + ch; cr++)
                    owners.set(`${cc},${cr}`, c);
        });

        let conflictCard = null;
        outer:
        for (let cc = newCol; cc < newCol + mw; cc++) {
            for (let cr = newRow; cr < newRow + mh; cr++) {
                const owner = owners.get(`${cc},${cr}`);
                if (owner) { conflictCard = owner; break outer; }
            }
        }

        if (!conflictCard) return [{ id: movedCard.id, col: newCol, row: newRow }];

        const occupied = new Set();
        others.forEach(c => {
            if (c.id === conflictCard.id) return;
            const [cw, ch] = sizeOf(c);
            const gc = c.grid_col || 1, gr = c.grid_row || 1;
            for (let cc = gc; cc < gc + cw; cc++)
                for (let cr = gr; cr < gr + ch; cr++)
                    occupied.add(`${cc},${cr}`);
        });
        for (let cc = newCol; cc < newCol + mw; cc++)
            for (let cr = newRow; cr < newRow + mh; cr++)
                occupied.add(`${cc},${cr}`);

        const [freeCol, freeRow] = this._findFreeSpot(
            conflictCard, movedCard.grid_col || 1, movedCard.grid_row || 1, occupied
        );
        return [
            { id: conflictCard.id, col: freeCol, row: freeRow },
            { id: movedCard.id, col: newCol, row: newRow },
        ];
    }

    _findFreeSpot(card, wantCol, wantRow, occupied) {
        const [cw, ch] = (card.size || '1x1').split('x').map(Number);
        const occ = occupied || new Set();
        if (!occupied) {
            this.cards.forEach(c => {
                if (c.id === card.id) return;
                const gc = c.grid_col || 1, gr = c.grid_row || 1;
                const [sc, sh] = (c.size || '1x1').split('x').map(Number);
                for (let cc = gc; cc < gc + sc; cc++)
                    for (let cr = gr; cr < gr + sh; cr++)
                        occ.add(`${cc},${cr}`);
            });
        }

        for (let offset = 0; offset < 200; offset++) {
            const candidates = offset === 0
                ? [[wantCol, wantRow]]
                : [[wantCol + offset, wantRow], [wantCol - offset, wantRow],
                   [wantCol, wantRow + offset], [wantCol, wantRow - offset],
                   [wantCol + offset, wantRow + offset], [wantCol - offset, wantRow - offset],
                   [wantCol + offset, wantRow - offset], [wantCol - offset, wantRow + offset]];

            for (const [tc, tr] of candidates) {
                if (tc < 1 || tr < 1 || tc + cw - 1 > this.gridCols) continue;
                let ok = true;
                for (let cc = tc; cc < tc + cw; cc++)
                    for (let cr = tr; cr < tr + ch; cr++)
                        if (occ.has(`${cc},${cr}`)) { ok = false; break; }
                    if (!ok) break;
                if (ok) return [tc, tr];
            }
        }
        const maxRow = Math.max(...this.cards.map(c => c.grid_row || 1), 1);
        return [1, maxRow + 1];
    }

    /* ==================== Buttons ==================== */
    _setupButtons() {
        document.getElementById('edit-mode-btn')?.addEventListener('click', () => {
            this.editMode = !this.editMode;
            localStorage.setItem('editMode', this.editMode);
            this._applyEditMode();
            this.renderCards();
        });

        document.getElementById('settings-btn')?.addEventListener('click', () => Components.showModal('settings-modal'));
        document.getElementById('add-card-btn')?.addEventListener('click', () => { this._resetCardModal(); Components.showModal('card-modal'); });

        this._setupBgUpload();
        this._setupCardModal();

        document.getElementById('blur-slider')?.addEventListener('input', e => {
            document.getElementById('blur-value').textContent = e.target.value + 'px';
            const url = this.settings?.background_image ? Components.resolveIconUrl(this.settings.background_image) : null;
            Components.updateBackground(url, parseInt(e.target.value));
        });
        document.getElementById('blur-slider')?.addEventListener('change', () => this._scheduleBlurSave());

        document.getElementById('theme-light')?.addEventListener('click', () => { Components.setTheme('light'); this._saveTheme('light'); });
        document.getElementById('theme-dark')?.addEventListener('click', () => { Components.setTheme('dark'); this._saveTheme('dark'); });

        document.getElementById('export-btn')?.addEventListener('click', () => this._export());
        document.getElementById('import-btn')?.addEventListener('click', () => document.getElementById('import-file-input')?.click());
        document.getElementById('import-file-input')?.addEventListener('change', e => this._import(e.target.files?.[0]));
    }

    _setupBgUpload() {
        const area = document.getElementById('bg-upload-area');
        const prev = document.getElementById('bg-upload-preview');
        const ph = document.getElementById('bg-upload-placeholder');
        const img = document.getElementById('bg-preview-img');
        const rm = document.getElementById('bg-remove-btn');

        Components.initFileUpload(area, 'bg-file-input', async file => {
            try {
                const r = await api.uploadImage(file);
                this.settings.background_image = r.filename;
                const blur = parseInt(document.getElementById('blur-slider').value) || 0;
                this.settings.blur_radius = blur;
                await api.updateSettings({ background_image: r.filename, blur_radius: blur });
                img.src = r.url; ph.style.display = 'none'; prev.style.display = 'block';
                Components.updateBackground(r.url, blur);
                Components.showToast('Background uploaded');
            } catch (err) {
                Components.showToast('Upload failed: ' + err.message, 'error');
            }
        });

        rm?.addEventListener('click', async e => {
            e.stopPropagation();
            if (!this.settings?.background_image) return;
            try {
                const blur = parseInt(document.getElementById('blur-slider').value) || 0;
                /* Clearing the setting also deletes the file server-side. */
                await api.updateSettings({ background_image: null, blur_radius: blur });
                this.settings.background_image = null;
                this.settings.blur_radius = blur;
                Components.updateBackground(null, blur);
                ph.style.display = 'flex'; prev.style.display = 'none';
                Components.showToast('Background removed');
            } catch (err) {
                Components.showToast('Failed: ' + err.message, 'error');
            }
        });
    }

    _setupCardModal() {
        const title = document.getElementById('card-title');
        const url = document.getElementById('card-url');
        const iconUrl = document.getElementById('card-icon-url');
        const save = document.getElementById('card-save-btn');
        const del = document.getElementById('card-delete-btn');
        const fetchBtn = document.getElementById('fetch-icon-btn');

        document.querySelectorAll('#size-selector .size-btn').forEach(b => {
            b.addEventListener('click', () => {
                document.querySelectorAll('#size-selector .size-btn').forEach(x => x.classList.remove('active'));
                b.classList.add('active');
                this._modalState.size = b.dataset.size;
            });
        });

        /* Open mode toggle (new tab vs same tab) */
        document.querySelectorAll('#open-mode-selector .btn-toggle').forEach(b => {
            b.addEventListener('click', () => {
                document.querySelectorAll('#open-mode-selector .btn-toggle').forEach(x => x.classList.remove('active'));
                b.classList.add('active');
                document.getElementById('card-new-tab').value = b.dataset.newTab;
            });
        });

        iconUrl?.addEventListener('input', () => {
            const v = iconUrl.value.trim();
            if (v) {
                this._modalState.iconFile = v;
                document.getElementById('icon-preview-img').src = v;
                document.getElementById('icon-upload-placeholder').style.display = 'none';
                document.getElementById('icon-upload-preview').style.display = 'block';
            }
        });

        Components.initFileUpload(document.getElementById('icon-upload-area'), 'icon-file-input', async file => {
            try {
                const r = await api.uploadImage(file);
                this._modalState.iconFile = r.filename;
                document.getElementById('icon-preview-img').src = r.url;
                document.getElementById('icon-upload-placeholder').style.display = 'none';
                document.getElementById('icon-upload-preview').style.display = 'block';
                if (iconUrl) iconUrl.value = '';
            } catch (err) {
                Components.showToast('Upload failed: ' + err.message, 'error');
            }
        });

        document.getElementById('icon-remove-btn')?.addEventListener('click', e => {
            e.stopPropagation();
            this._modalState.iconFile = null;
            document.getElementById('icon-upload-placeholder').style.display = 'flex';
            document.getElementById('icon-upload-preview').style.display = 'none';
            if (iconUrl) iconUrl.value = '';
        });

        fetchBtn?.addEventListener('click', async () => {
            const u = url.value.trim();
            if (!u) { Components.showToast('Enter URL first', 'error'); return; }
            fetchBtn.disabled = true; fetchBtn.textContent = 'Loading';
            try {
                const r = await api.fetchIcon(u);
                if (r.icon_path) {
                    this._modalState.iconFile = r.icon_path;
                    document.getElementById('icon-preview-img').src = Components.resolveIconUrl(r.icon_path);
                    document.getElementById('icon-upload-placeholder').style.display = 'none';
                    document.getElementById('icon-upload-preview').style.display = 'block';
                    if (iconUrl) iconUrl.value = '';
                    Components.showToast('Icon fetched');
                } else Components.showToast('No icon found', 'error');
            } catch (err) {
                Components.showToast('Failed: ' + err.message, 'error');
            } finally {
                fetchBtn.disabled = false; fetchBtn.textContent = 'Fetch';
            }
        });

        save?.addEventListener('click', async () => {
            const t = title.value.trim();
            if (!t) { Components.showToast('Enter title', 'error'); return; }
            const typedIconUrl = iconUrl?.value.trim();
            const data = {
                title: t,
                url: url.value.trim() || null,
                size: this._modalState.size,
                icon_path: typedIconUrl || this._modalState.iconFile || null,
                grid_col: parseInt(document.getElementById('card-grid-col').value) || 1,
                grid_row: parseInt(document.getElementById('card-grid-row').value) || 1,
                open_in_new_tab: document.getElementById('card-new-tab').value !== 'false',
            };
            save.disabled = true;
            try {
                if (this.editingCard) { await api.updateCard(this.editingCard.id, data); Components.showToast('Updated'); }
                else { await api.createCard(data); Components.showToast('Created'); }
                Components.hideModal('card-modal');
                this._resetCardModal();
                await this.loadCards();
            } catch (e) {
                Components.showToast(e.message || 'Failed', 'error');
            } finally {
                save.disabled = false;
            }
        });

        del?.addEventListener('click', async () => {
            if (!this.editingCard) return;
            await this._deleteCard(this.editingCard);
            Components.hideModal('card-modal');
            this._resetCardModal();
        });
    }

    /* Sync the open-mode toggle UI + hidden input to a boolean */
    _setOpenMode(newTab) {
        const val = newTab !== false;
        document.getElementById('card-new-tab').value = val ? 'true' : 'false';
        const nb = document.getElementById('open-mode-new');
        const sb = document.getElementById('open-mode-same');
        if (nb && sb) {
            nb.classList.toggle('active', val);
            sb.classList.toggle('active', !val);
        }
    }

    _resetCardModal() {
        this._modalState = { size: '1x1', iconFile: null };
        document.getElementById('card-title').value = '';
        document.getElementById('card-url').value = '';
        const iconUrl = document.getElementById('card-icon-url');
        if (iconUrl) iconUrl.value = '';
        document.getElementById('card-grid-col').value = 1;
        document.getElementById('card-grid-row').value = 1;
        this._setOpenMode(true);
        document.getElementById('card-delete-btn').style.display = 'none';
        document.getElementById('card-modal-title').textContent = 'Add Card';
        this.editingCard = null;
        document.querySelectorAll('#size-selector .size-btn').forEach(b => b.classList.toggle('active', b.dataset.size === '1x1'));
        document.getElementById('icon-upload-placeholder').style.display = 'flex';
        document.getElementById('icon-upload-preview').style.display = 'none';
        document.getElementById('icon-preview-img').src = '';
    }

    /* ==================== Modals ==================== */
    _setupModals() {
        document.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click', () => Components.hideModal(b.dataset.close)));
        document.querySelectorAll('.modal-overlay').forEach(o => o.addEventListener('click', e => { if (e.target === o) Components.hideModal(o.id); }));
        document.addEventListener('keydown', e => {
            if (e.key !== 'Escape') return;
            const active = document.querySelectorAll('.modal-overlay.active');
            if (active.length) Components.hideModal(active[active.length - 1].id);
        });
    }

    /* ==================== Authentication ==================== */
    _setupLogin() {
        document.getElementById('auth-form')?.addEventListener('submit', async e => {
            e.preventDefault();
            const input = document.getElementById('auth-token-input');
            const token = input.value.trim();
            if (!token) return;
            api.setAuthToken(token);
            Components.hideModal('auth-modal');
            await this.loadData();
        });
    }

    _showLogin(message) {
        const error = document.getElementById('auth-error');
        if (error) error.textContent = message || '';
        const input = document.getElementById('auth-token-input');
        if (input) input.value = '';
        if (document.getElementById('auth-modal')) Components.showModal('auth-modal');
    }

    /* ==================== Search ==================== */
    _updateEngineIcon() { const i = document.getElementById('search-engine-icon'); if (i) i.src = this._engineIcon(this.searchEngine); }

    async _suggestions(q) {
        if (q.length < 2) return [];
        /* Cancel any in-flight suggestion request to avoid races / piled-up promises */
        if (this._suggestController) this._suggestController.abort();
        const controller = new AbortController();
        this._suggestController = controller;
        try {
            const r = await fetch(`https://en.wikipedia.org/w/api.php?action=opensearch&search=${encodeURIComponent(q)}&limit=8&format=json&origin=*`, { signal: controller.signal });
            const d = await r.json();
            return d[1] || [];
        } catch (e) {
            if (e.name === 'AbortError') return null; // superseded — caller ignores
            return [];
        } finally {
            if (this._suggestController === controller) this._suggestController = null;
        }
    }

    _setupSearch() {
        const inp = document.getElementById('search-input');
        const sug = document.getElementById('search-suggestions');
        const eng = document.getElementById('search-engine-btn');
        const dd = document.getElementById('engine-dropdown');

        const openSearch = text => {
            if (!text) return;
            window.open(this.searchUrl + encodeURIComponent(text), '_blank', 'noopener,noreferrer');
        };

        inp?.addEventListener('input', () => {
            const q = inp.value.trim();
            if (q.length < 2) { sug.classList.remove('show'); return; }
            clearTimeout(this.searchTimeout);
            this.searchTimeout = setTimeout(async () => {
                const res = await this._suggestions(q);
                if (res === null) return; // request was superseded; leave UI untouched
                if (res.length) {
                    Components.renderSuggestions(sug, res, text => {
                        sug.classList.remove('show');
                        inp.value = text;
                        openSearch(text);
                    });
                    sug.classList.add('show');
                } else sug.classList.remove('show');
            }, 300);
        });

        inp?.addEventListener('keydown', e => {
            if (e.key === 'Enter') { const q = inp.value.trim(); sug.classList.remove('show'); openSearch(q); }
            else if (e.key === 'Escape') { sug.classList.remove('show'); inp.blur(); }
        });
        inp?.addEventListener('blur', () => {
            setTimeout(() => { sug.classList.remove('show'); clearTimeout(this.searchTimeout); }, 150);
        });
        document.getElementById('search-submit-btn')?.addEventListener('click', () => openSearch(inp.value.trim()));

        eng?.addEventListener('click', e => {
            e.stopPropagation();
            dd.classList.toggle('show');
            eng.setAttribute('aria-expanded', dd.classList.contains('show') ? 'true' : 'false');
        });
        eng?.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); eng.click(); }
        });
        dd?.querySelectorAll('.search-engine-option').forEach(o => {
            o.addEventListener('keydown', e => {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); o.click(); }
            });
        });
        dd?.querySelectorAll('.search-engine-option').forEach(o => o.addEventListener('click', () => {
            this.searchEngine = o.dataset.engine;
            this.searchUrl = this._engineUrl(this.searchEngine);
            localStorage.setItem('searchEngine', this.searchEngine);
            this._updateEngineIcon();
            dd.classList.remove('show');
            eng?.setAttribute('aria-expanded', 'false');
        }));
        document.addEventListener('click', e => {
            if (!e.target.closest('.search-engine-select') && !e.target.closest('.search-engine-dropdown')) {
                dd?.classList.remove('show');
                eng?.setAttribute('aria-expanded', 'false');
            }
        });
    }

    /* ==================== Data Loading ==================== */
    async loadData() {
        try {
            const d = await api.getFullData();
            this.settings = d.settings;
            this.cards = d.cards;
            /* Resolve overlaps locally, render immediately, persist in background */
            this._autoSpreadCards();
            this._applySettings();
            this.renderCards();
        } catch (error) {
            if (error.status === 401) {
                this._showLogin('Enter the API token to continue');
                return;
            }
            Components.showToast('Failed to load data: ' + error.message, 'error');
            this.settings = { background_image: null, blur_radius: 0, dark_mode: false };
            this.cards = [];
            Components.renderErrorState(document.getElementById('cards-grid'), () => this.loadData());
        }
    }

    /**
     * Resolve cards that share a grid cell. Computes new positions synchronously
     * (no network round-trips on the critical path), updates local state so the
     * first render is already correct, then persists the moves concurrently in
     * the background — start-up never blocks on the server.
     */
    _autoSpreadCards() {
        const cols = Math.max(1, this.gridCols);
        const occupied = new Set();
        const toSpread = [];

        const fits = (card, col, row) => {
            const [w, h] = (card.size || '1x1').split('x').map(Number);
            if (col < 1 || row < 1 || col + w - 1 > cols) return false;
            for (let cc = col; cc < col + w; cc++)
                for (let cr = row; cr < row + h; cr++)
                    if (occupied.has(`${cc},${cr}`)) return false;
            return true;
        };
        const occupy = (card, col, row) => {
            const [w, h] = (card.size || '1x1').split('x').map(Number);
            for (let cc = col; cc < col + w; cc++)
                for (let cr = row; cr < row + h; cr++) occupied.add(`${cc},${cr}`);
        };

        this.cards.forEach(c => {
            const col = c.grid_col || 1, row = c.grid_row || 1;
            if (fits(c, col, row)) occupy(c, col, row);
            else toSpread.push(c);
        });

        if (toSpread.length === 0) return;

        const moves = [];
        for (const card of toSpread) {
            let placed = false;
            for (let row = 1; row < 200 && !placed; row++) {
                for (let col = 1; col <= cols && !placed; col++) {
                    if (fits(card, col, row)) {
                        occupy(card, col, row);
                        card.grid_col = col;
                        card.grid_row = row;
                        moves.push({ id: card.id, col, row });
                        placed = true;
                    }
                }
            }
        }

        if (moves.length === 0) return;

        /* Persist in the background; do not block startup or rendering */
        this._persistMoves(moves);
    }

    async _persistMoves(moves) {
        const results = await Promise.allSettled(
            moves.map(m => api.updateCard(m.id, { grid_col: m.col, grid_row: m.row }))
        );
        const failCount = results.filter(r => r.status === 'rejected').length;
        const successCount = results.length - failCount;
        if (failCount > 0) {
            results.forEach((r, i) => { if (r.status === 'rejected') console.error('[auto-spread] failed', moves[i].id, r.reason); });
            Components.showToast(`Spread ${successCount} of ${moves.length} overlapping cards (${failCount} failed)`, 'error');
            /* Some moves were not persisted — resync local state with the server
             * so the optimistic layout doesn't diverge from what's stored. */
            try {
                this.cards = await api.getCards();
                this.renderCards();
            } catch (_) { /* leave optimistic state if reload also fails */ }
        } else {
            Components.showToast(`Spread ${successCount} overlapping cards`);
        }
    }

    _applySettings() {
        const bgUrl = this.settings.background_image ? Components.resolveIconUrl(this.settings.background_image) : null;
        Components.updateBackground(bgUrl, this.settings.blur_radius || 0);
        const s = document.getElementById('blur-slider');
        if (s) { s.value = this.settings.blur_radius || 0; document.getElementById('blur-value').textContent = (this.settings.blur_radius || 0) + 'px'; }
        if (this.settings.background_image) {
            const p = document.getElementById('bg-upload-preview');
            const h = document.getElementById('bg-upload-placeholder');
            const i = document.getElementById('bg-preview-img');
            if (p && h && i) {
                i.src = Components.resolveIconUrl(this.settings.background_image);
                h.style.display = 'none';
                p.style.display = 'block';
            }
        }
        Components.setTheme(this.settings.dark_mode ? 'dark' : 'light');
    }

    renderCards() {
        Components.renderCards(
            this.cards,
            document.getElementById('cards-grid'),
            card => this._editCard(card),
            card => this._deleteCard(card),
            this.editMode,
            this.gridCols
        );
    }

    async loadCards() {
        try {
            this.cards = await api.getCards();
            this.renderCards();
        } catch (error) {
            Components.showToast('Failed to load cards: ' + error.message, 'error');
        }
    }

    _editCard(card) {
        this.editingCard = card;
        this._modalState = { size: card.size || '1x1', iconFile: card.icon_path || null };
        document.getElementById('card-modal-title').textContent = 'Edit Card';
        document.getElementById('card-title').value = card.title;
        document.getElementById('card-url').value = card.url || '';
        document.getElementById('card-delete-btn').style.display = 'block';
        document.querySelectorAll('#size-selector .size-btn').forEach(b => b.classList.toggle('active', b.dataset.size === (card.size || '1x1')));
        document.getElementById('card-grid-col').value = card.grid_col || 1;
        document.getElementById('card-grid-row').value = card.grid_row || 1;
        this._setOpenMode(card.open_in_new_tab !== false);
        const iconUrl = document.getElementById('card-icon-url');
        if (card.icon_path) {
            document.getElementById('icon-preview-img').src = Components.resolveIconUrl(card.icon_path);
            document.getElementById('icon-upload-placeholder').style.display = 'none';
            document.getElementById('icon-upload-preview').style.display = 'block';
            if (iconUrl) iconUrl.value = /^https?:\/\//i.test(card.icon_path) ? card.icon_path : '';
        } else {
            document.getElementById('icon-upload-placeholder').style.display = 'flex';
            document.getElementById('icon-upload-preview').style.display = 'none';
            if (iconUrl) iconUrl.value = '';
        }
        Components.showModal('card-modal');
    }

    async _deleteCard(card) {
        if (!card || !confirm('Delete this card?')) return;
        try {
            await api.deleteCard(card.id);
            Components.showToast('Card deleted');
            await this.loadCards();
        } catch (error) {
            Components.showToast('Failed to delete: ' + error.message, 'error');
        }
    }

    _scheduleBlurSave() {
        clearTimeout(this._blurTimer);
        this._blurTimer = setTimeout(() => this._saveBlur(), 250);
    }

    async _saveBlur() {
        try {
            const value = parseInt(document.getElementById('blur-slider').value);
            await api.updateSettings({ blur_radius: value });
            this.settings.blur_radius = value;
        } catch (error) {
            Components.showToast('Blur not saved: ' + error.message, 'error');
        }
    }

    async _saveTheme(theme) {
        const previous = this.settings?.dark_mode ? 'dark' : 'light';
        try {
            await api.updateSettings({ dark_mode: theme === 'dark' });
            if (this.settings) this.settings.dark_mode = theme === 'dark';
        } catch (error) {
            Components.setTheme(previous);
            Components.showToast('Theme not saved: ' + error.message, 'error');
        }
    }

    _export() {
        const blob = new Blob(
            [JSON.stringify({ settings: this.settings, cards: this.cards, exportedAt: new Date().toISOString() }, null, 2)],
            { type: 'application/json' }
        );
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'homepage-backup-' + new Date().toISOString().split('T')[0] + '.json';
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        Components.showToast('Exported');
    }

    async _import(file) {
        if (!file) return;
        try {
            const parsed = JSON.parse(await file.text());
            if (!parsed || !Array.isArray(parsed.cards)) throw new Error('Invalid backup file');
            const settings = parsed.settings ? {
                background_image: parsed.settings.background_image ?? null,
                blur_radius: Number.isFinite(parsed.settings.blur_radius) ? parsed.settings.blur_radius : 0,
                dark_mode: !!parsed.settings.dark_mode,
            } : null;
            const cards = parsed.cards.map(c => ({
                title: typeof c.title === 'string' ? c.title : '',
                url: c.url ?? null,
                icon_path: c.icon_path ?? null,
                size: c.size || '1x1',
                grid_col: c.grid_col ?? 1,
                grid_row: c.grid_row ?? 1,
                open_in_new_tab: c.open_in_new_tab !== false,
            }));
            await api.importData({ settings, cards });
            Components.showToast('Imported');
            await this.loadData();
        } catch (error) {
            Components.showToast('Import failed: ' + error.message, 'error');
        }
        document.getElementById('import-file-input').value = '';
    }
}

document.addEventListener('DOMContentLoaded', () => { window.App = new HomepageApp(); });
