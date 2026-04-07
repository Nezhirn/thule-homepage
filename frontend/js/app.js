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

        // Drag & drop state (single shared instance)
        this._drag = { active: false, ghost: null, cursor: null, card: null, sx: 0, sy: 0, ox: 0, oy: 0 };

        this.init();
    }

    /* Detect grid columns from actual CSS computed style */
    _detectGridCols() {
        const grid = document.getElementById('cards-grid');
        if (grid) {
            const val = parseInt(getComputedStyle(grid).gridTemplateColumns.split(' ').length);
            if (val > 0) { this.gridCols = val; return; }
        }
        const w = window.innerWidth;
        if (w <= 480) this.gridCols = 2;
        else if (w <= 768) this.gridCols = 3;
        else if (w <= 1024) this.gridCols = 4;
        else this.gridCols = 7;
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
    _cleanupDrag() {
        const d = this._drag;
        if (d.cursor) { d.cursor.remove(); d.cursor = null; }
        if (d.ghost) {
            if (d.ghost.parentNode) d.ghost.parentNode.removeChild(d.ghost);
            d.ghost = null;
        }
    }

    _initDragDrop() {
        const grid = document.getElementById('cards-grid');
        const d = this._drag;

        const startDrag = (clientX, clientY, card) => {
            if (!this.editMode) return;
            const rect = card.getBoundingClientRect();
            d.active = true; d.card = card;
            d.sx = clientX; d.sy = clientY;
            d.ox = rect.left; d.oy = rect.top;
            d.targetCol = null; d.targetRow = null;

            d.ghost = card.cloneNode(true);
            Object.assign(d.ghost.style, {
                position: 'fixed', width: rect.width + 'px', height: rect.height + 'px',
                left: rect.left + 'px', top: rect.top + 'px', opacity: '0.85',
                pointerEvents: 'none', zIndex: '9999',
                boxShadow: '0 16px 48px rgba(0,0,0,0.3)', transform: 'scale(1.05)',
                transition: 'none', margin: '0'
            });
            document.body.appendChild(d.ghost);
            card.style.opacity = '0.3';
        };

        const moveDrag = (clientX, clientY) => {
            if (!d.active || !d.ghost) return;
            d.ghost.style.left = (d.ox + clientX - d.sx) + 'px';
            d.ghost.style.top  = (d.oy + clientY - d.sy) + 'px';

            grid.querySelectorAll('.cell-highlight').forEach(c => c.classList.remove('cell-highlight'));
            grid.querySelectorAll('.card.drag-over').forEach(c => c.classList.remove('drag-over'));
            if (d.cursor) d.cursor.remove();
            d.cursor = null;

            d.ghost.style.display = 'none';
            const el = document.elementFromPoint(clientX, clientY);
            d.ghost.style.display = '';

            const targetCell = el?.closest('.grid-cell');
            const targetCard = el?.closest('.card');

            if (targetCell) {
                targetCell.classList.add('cell-highlight');
                d.targetCol = parseInt(targetCell.dataset.col);
                d.targetRow = parseInt(targetCell.dataset.row);
            } else if (targetCard && targetCard !== d.card) {
                targetCard.classList.add('drag-over');
                const tid = parseInt(targetCard.dataset.id);
                const tc = this.cards.find(c => c.id === tid);
                d.targetCol = tc?.grid_col || 1;
                d.targetRow = tc?.grid_row || 1;
            } else {
                const [col, row] = this._calcGridPos(clientX, clientY);
                d.targetCol = col; d.targetRow = row;
                d.cursor = this._makeCursorIndicator();
                const gridRect = grid.getBoundingClientRect();
                const style = getComputedStyle(grid);
                const gap = parseFloat(style.gap) || 16;
                const paddingLeft = parseFloat(style.paddingLeft) || parseFloat(style.padding) || 16;
                const cellH = Math.round(gridRect.height / Math.max(1, parseFloat(style.gridAutoRows) || 160));
                const usableWidth = gridRect.width - paddingLeft * 2 - gap * 2;
                const colWidth = usableWidth / this.gridCols;
                const x = paddingLeft + (col - 1) * (colWidth + gap) + colWidth / 2;
                const y = parseFloat(style.paddingTop) + (row - 1) * (cellH + gap) + cellH / 2;
                d.cursor.style.left = (gridRect.left + x) + 'px';
                d.cursor.style.top = (gridRect.top + y) + 'px';
                d.cursor.style.width = colWidth + 'px';
                d.cursor.style.height = cellH + 'px';
                document.body.appendChild(d.cursor);
            }
        };

        const endDrag = async () => {
            if (!d.active) return;

            if (d.ghost) {
                d.ghost.style.display = 'none';
                const movedCardId = parseInt(d.card.dataset.id);
                const movedCard = this.cards.find(c => c.id === movedCardId);

                if (movedCard && d.targetCol !== null && d.targetRow !== null) {
                    const origCol = movedCard.grid_col;
                    const origRow = movedCard.grid_row;
                    const [col, row] = this._resolveCollision(movedCard, d.targetCol, d.targetRow);

                    try {
                        await api.updateCard(movedCardId, { grid_col: col, grid_row: row });
                        movedCard.grid_col = col;
                        movedCard.grid_row = row;
                        Components.showToast('Card moved to (' + col + ',' + row + ')');
                    } catch (err) {
                        movedCard.grid_col = origCol;
                        movedCard.grid_row = origRow;
                        Components.showToast('Failed: ' + err.message, 'error');
                    }
                    this.renderCards();
                }
            }

            this._cleanupDrag();
            if (d.card) d.card.style.opacity = '';
            grid.querySelectorAll('.cell-highlight').forEach(c => c.classList.remove('cell-highlight'));
            grid.querySelectorAll('.card.drag-over').forEach(c => c.classList.remove('drag-over'));
            d.active = false; d.card = null; d.targetCol = null; d.targetRow = null;
        };

        /* Mouse events */
        grid.addEventListener('mousedown', e => {
            if (!this.editMode) return;
            const card = e.target.closest('.card');
            if (!card) return;
            if (e.target.closest('.card-menu-btn') || e.target.closest('.card-dropdown')) return;
            startDrag(e.clientX, e.clientY, card);
            e.preventDefault();
        });
        document.addEventListener('mousemove', e => moveDrag(e.clientX, e.clientY));
        document.addEventListener('mouseup', endDrag);

        /* Touch events */
        let touchStartTimer = null;
        let touchHandled = false;
        grid.addEventListener('touchstart', e => {
            if (!this.editMode) return;
            const card = e.target.closest('.card');
            if (!card) return;
            if (e.target.closest('.card-menu-btn') || e.target.closest('.card-dropdown')) return;
            const touch = e.touches[0];
            touchHandled = false;
            touchStartTimer = setTimeout(() => {
                touchHandled = true;
                startDrag(touch.clientX, touch.clientY, card);
            }, 300);
        }, { passive: true });
        grid.addEventListener('touchmove', e => {
            if (!d.active) { clearTimeout(touchStartTimer); return; }
            if (d.active) e.preventDefault();
            moveDrag(e.touches[0].clientX, e.touches[0].clientY);
        }, { passive: false });
        grid.addEventListener('touchend', () => { clearTimeout(touchStartTimer); if (touchHandled) { endDrag(); touchHandled = false; } });
        grid.addEventListener('touchcancel', () => { clearTimeout(touchStartTimer); if (touchHandled) { endDrag(); touchHandled = false; } });
    }

    /* Calculate grid column/row from absolute coordinates */
    _calcGridPos(mx, my) {
        const grid = document.getElementById('cards-grid');
        const gridRect = grid.getBoundingClientRect();
        const style = getComputedStyle(grid);
        const cols = style.gridTemplateColumns.split(' ').length;
        this.gridCols = cols;

        const gap = parseFloat(style.gap) || 16;
        const paddingTop = parseFloat(style.paddingTop) || parseFloat(style.padding) || 16;
        const cellH = Math.round(gridRect.height / Math.max(1, parseFloat(style.gridAutoRows) || 160));

        const usableWidth = gridRect.width - gap * (cols - 1);
        const colWidth = usableWidth / cols;
        const col = Math.floor((mx - gridRect.left - paddingTop) / (colWidth + gap)) + 1;
        const row = Math.floor((my - gridRect.top - paddingTop) / (cellH + gap)) + 1;
        return [Math.max(1, Math.min(col, cols)), Math.max(1, row)];
    }

    /* Create drop-target cursor indicator */
    _makeCursorIndicator() {
        const el = document.createElement('div');
        Object.assign(el.style, {
            position: 'fixed', border: '2px solid var(--accent)',
            background: 'rgba(53, 132, 228, 0.1)',
            borderRadius: 'var(--radius-xl, 24px)',
            pointerEvents: 'none', zIndex: '9998', transition: 'none'
        });
        return el;
    }

    /* ==================== Collision Resolution ==================== */
    _resolveCollision(movedCard, newCol, newRow) {
        const [mw, mh] = (movedCard.size || '1x1').split('x').map(Number);

        const occupied = new Map();
        this.cards.forEach(c => {
            if (c.id === movedCard.id) return;
            const gc = c.grid_col || 1, gr = c.grid_row || 1;
            const [cw, ch] = (c.size || '1x1').split('x').map(Number);
            for (let cc = gc; cc < gc + cw; cc++)
                for (let cr = gr; cr < gr + ch; cr++)
                    occupied.set(`${cc},${cr}`, c);
        });

        let conflict = false, conflictCard = null;
        for (let cc = newCol; cc < newCol + mw; cc++) {
            for (let cr = newRow; cr < newRow + mh; cr++) {
                const key = `${cc},${cr}`;
                if (occupied.has(key)) { conflict = true; if (!conflictCard) conflictCard = occupied.get(key); }
            }
            if (conflict) break;
        }

        if (!conflict) return [newCol, newRow];

        if (conflictCard) {
            const oldCol = movedCard.grid_col || 1, oldRow = movedCard.grid_row || 1;
            const [freeCol, freeRow] = this._findFreeSpot(conflictCard, oldCol, oldRow);

            api.updateCard(conflictCard.id, { grid_col: freeCol, grid_row: freeRow }).catch(err => {
                console.warn('[collision] Failed to reposition conflict card', conflictCard.id, err);
            });

            conflictCard.grid_col = freeCol;
            conflictCard.grid_row = freeRow;
            return [newCol, newRow];
        }

        return this._findFreeSpot(movedCard, newCol, newRow);
    }

    _findFreeSpot(card, wantCol, wantRow) {
        const [cw, ch] = (card.size || '1x1').split('x').map(Number);
        const occ = new Set();
        this.cards.forEach(c => {
            if (c.id === card.id) return;
            const gc = c.grid_col || 1, gr = c.grid_row || 1;
            const [sc, sh] = (c.size || '1x1').split('x').map(Number);
            for (let cc = gc; cc < gc + sc; cc++)
                for (let cr = gr; cr < gr + sh; cr++)
                    occ.add(`${cc},${cr}`);
        });

        for (let offset = 0; offset < 200; offset++) {
            const candidates = offset === 0
                ? [[wantCol, wantRow]]
                : [[wantCol + offset, wantRow], [wantCol - offset, wantRow],
                   [wantCol, wantRow + offset], [wantCol, wantRow - offset],
                   [wantCol + offset, wantRow + offset], [wantCol - offset, wantRow - offset],
                   [wantCol + offset, wantRow - offset], [wantCol - offset, wantRow + offset]];

            for (const [tc, tr] of candidates) {
                if (tc < 1 || tr < 1) continue;
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
            const url = this.settings?.background_image ? '/api/uploads/' + this.settings.background_image : null;
            Components.updateBackground(url, parseInt(e.target.value));
        });
        document.getElementById('blur-slider')?.addEventListener('change', () => this._saveBlur());

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
            } catch (err) { console.error('[bg-upload] error', err); Components.showToast('Upload failed: ' + err.message, 'error'); }
        });

        rm?.addEventListener('click', async e => {
            e.stopPropagation();
            if (!this.settings?.background_image) return;
            try {
                const filename = this.settings.background_image;
                const cleanName = filename.startsWith('/') ? filename.split('/').pop() : filename;
                try { await api.deleteImage(cleanName); } catch (e) { if (!e.message.includes('File not found')) throw e; }
                this.settings.background_image = null;
                const blur = parseInt(document.getElementById('blur-slider').value) || 0;
                this.settings.blur_radius = blur;
                await api.updateSettings({ background_image: null, blur_radius: blur });
                Components.updateBackground(null, blur);
                ph.style.display = 'flex'; prev.style.display = 'none';
                Components.showToast('Background removed');
            } catch (err) {
                console.error('[bg-remove] error', err);
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

        let size = '1x1', iconFile = null;

        document.querySelectorAll('#size-selector .size-btn').forEach(b => {
            b.addEventListener('click', () => {
                document.querySelectorAll('#size-selector .size-btn').forEach(x => x.classList.remove('active'));
                b.classList.add('active'); size = b.dataset.size;
            });
        });

        iconUrl?.addEventListener('input', () => {
            const v = iconUrl.value.trim();
            if (v) {
                document.getElementById('icon-preview-img').src = v;
                document.getElementById('icon-upload-placeholder').style.display = 'none';
                document.getElementById('icon-upload-preview').style.display = 'block';
                iconFile = v;
            }
        });

        Components.initFileUpload(document.getElementById('icon-upload-area'), 'icon-file-input', async file => {
            try {
                const r = await api.uploadImage(file);
                iconFile = r.filename;
                document.getElementById('icon-preview-img').src = r.url;
                document.getElementById('icon-upload-placeholder').style.display = 'none';
                document.getElementById('icon-upload-preview').style.display = 'block';
                if (iconUrl) iconUrl.value = '';
            } catch (_) { Components.showToast('Upload failed', 'error'); }
        });

        document.getElementById('icon-remove-btn')?.addEventListener('click', e => {
            e.stopPropagation(); iconFile = null;
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
                    iconFile = r.icon_path;
                    document.getElementById('icon-preview-img').src = '/api/uploads/' + r.icon_path;
                    document.getElementById('icon-upload-placeholder').style.display = 'none';
                    document.getElementById('icon-upload-preview').style.display = 'block';
                    if (iconUrl) iconUrl.value = '';
                    Components.showToast('Icon fetched');
                } else Components.showToast('No icon found', 'error');
            } catch (_) { Components.showToast('Failed', 'error'); }
            finally { fetchBtn.disabled = false; fetchBtn.textContent = 'Fetch'; }
        });

        save?.addEventListener('click', async () => {
            const t = title.value.trim();
            if (!t) { Components.showToast('Enter title', 'error'); return; }
            const cu = iconUrl?.value.trim();
            const gCol = parseInt(document.getElementById('card-grid-col').value) || 1;
            const gRow = parseInt(document.getElementById('card-grid-row').value) || 1;
            const data = { title: t, url: url.value.trim() || null, size, icon_path: cu || iconFile || null, grid_col: gCol, grid_row: gRow };
            try {
                if (this.editingCard) { await api.updateCard(this.editingCard.id, data); Components.showToast('Updated'); }
                else { await api.createCard(data); Components.showToast('Created'); }
                Components.hideModal('card-modal');
                this._resetCardModal();
                await this.loadCards();
            } catch (e) { Components.showToast(e.message || 'Failed', 'error'); }
        });

        del?.addEventListener('click', async () => {
            if (this.editingCard && confirm('Delete?')) {
                try { await api.deleteCard(this.editingCard.id); Components.hideModal('card-modal'); this._resetCardModal(); await this.loadCards(); Components.showToast('Deleted'); }
                catch (_) { Components.showToast('Failed', 'error'); }
            }
        });
    }

    _resetCardModal() {
        document.getElementById('card-id').value = '';
        document.getElementById('card-title').value = '';
        document.getElementById('card-url').value = '';
        const iconUrl = document.getElementById('card-icon-url');
        if (iconUrl) iconUrl.value = '';
        document.getElementById('card-grid-col').value = 1;
        document.getElementById('card-grid-row').value = 1;
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
        document.addEventListener('keydown', e => { if (e.key === 'Escape') document.querySelectorAll('.modal-overlay.active').forEach(m => Components.hideModal(m.id)); });
    }

    /* ==================== Search ==================== */
    _updateEngineIcon() { const i = document.getElementById('search-engine-icon'); if (i) i.src = this._engineIcon(this.searchEngine); }

    async _suggestions(q) {
        if (q.length < 2) return [];
        try { const r = await fetch(`https://en.wikipedia.org/w/api.php?action=opensearch&search=${encodeURIComponent(q)}&limit=8&format=json&origin=*`); const d = await r.json(); return d[1] || []; }
        catch { return []; }
    }

    _setupSearch() {
        const inp = document.getElementById('search-input');
        const sug = document.getElementById('search-suggestions');
        const eng = document.getElementById('search-engine-btn');
        const dd = document.getElementById('engine-dropdown');

        inp?.addEventListener('input', () => {
            const q = inp.value.trim();
            if (q.length < 2) { sug.classList.remove('show'); return; }
            clearTimeout(this.searchTimeout);
            this.searchTimeout = setTimeout(async () => {
                const res = await this._suggestions(q);
                if (res.length) {
                    sug.innerHTML = res.map(r => `<div class="suggestion-item" data-q="${this._esc(r)}"><span class="suggestion-text">${this._esc(r)}</span></div>`).join('');
                    sug.classList.add('show');
                } else sug.classList.remove('show');
            }, 300);
        });

        sug?.addEventListener('click', e => {
            const i = e.target.closest('.suggestion-item');
            if (i) { sug.classList.remove('show'); inp.value = i.dataset.q; window.open(this.searchUrl + encodeURIComponent(i.dataset.q), '_blank', 'noopener,noreferrer'); }
        });
        inp?.addEventListener('keydown', e => {
            if (e.key === 'Enter') { const q = inp.value.trim(); sug.classList.remove('show'); if (q) window.open(this.searchUrl + encodeURIComponent(q), '_blank', 'noopener,noreferrer'); }
            else if (e.key === 'Escape') { sug.classList.remove('show'); inp.blur(); }
        });
        inp?.addEventListener('blur', () => {
            setTimeout(() => { sug.classList.remove('show'); clearTimeout(this.searchTimeout); }, 150);
        });
        document.getElementById('search-submit-btn')?.addEventListener('click', () => { const q = inp.value.trim(); if (q) window.open(this.searchUrl + encodeURIComponent(q), '_blank', 'noopener,noreferrer'); });

        eng?.addEventListener('click', e => { e.stopPropagation(); dd.classList.toggle('show'); });
        dd?.querySelectorAll('.search-engine-option').forEach(o => o.addEventListener('click', () => {
            this.searchEngine = o.dataset.engine;
            this.searchUrl = this._engineUrl(this.searchEngine);
            localStorage.setItem('searchEngine', this.searchEngine);
            this._updateEngineIcon();
            dd.classList.remove('show');
        }));
        document.addEventListener('click', e => { if (!e.target.closest('.search-engine-select') && !e.target.closest('.search-engine-dropdown')) dd?.classList.remove('show'); });
    }

    _esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

    /* ==================== Data Loading ==================== */
    async loadData() {
        try {
            const d = await api.getFullData();
            this.settings = d.settings;
            this.cards = d.cards;
            this._autoSpreadCards();
            this._applySettings();
            this.renderCards();
        } catch (_) {
            Components.showToast('Failed to load', 'error');
            this.settings = { background_image: null, blur_radius: 0, dark_mode: false };
            this.cards = [];
        }
    }

    async _autoSpreadCards() {
        const cols = this.gridCols;
        const occupied = new Set();
        const toSpread = [];

        this.cards.forEach(c => {
            const key = `${c.grid_col || 1},${c.grid_row || 1}`;
            if (occupied.has(key)) { toSpread.push(c); }
            else { occupied.add(key); }
        });

        if (toSpread.length === 0) return;

        let successCount = 0, failCount = 0;

        for (const card of toSpread) {
            let placed = false;
            for (let row = 1; row < 100 && !placed; row++) {
                for (let col = 1; col <= cols && !placed; col++) {
                    const key = `${col},${row}`;
                    if (!occupied.has(key)) {
                        occupied.add(key);
                        try {
                            await api.updateCard(card.id, { grid_col: col, grid_row: row });
                            card.grid_col = col;
                            card.grid_row = row;
                            successCount++;
                            placed = true;
                        } catch (err) {
                            console.error('[auto-spread] failed', card.id, err);
                            failCount++;
                        }
                    }
                }
            }
        }

        if (failCount > 0) {
            Components.showToast(`Spread ${successCount} of ${toSpread.length} overlapping cards (${failCount} failed)`, 'error');
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
            if (p && h && i) { i.src = '/api/uploads/' + this.settings.background_image; h.style.display = 'none'; p.style.display = 'block'; }
        }
        Components.setTheme(this.settings.dark_mode ? 'dark' : 'light');
    }

    renderCards() {
        Components.renderCards(this.cards, document.getElementById('cards-grid'), c => this._editCard(c), this.editMode, this.gridCols);
    }

    async loadCards() { try { this.cards = await api.getCards(); this.renderCards(); } catch (_) { console.error('load cards', _); } }

    openSettings() { Components.showModal('settings-modal'); }

    _editCard(card) {
        this.editingCard = card;
        document.getElementById('card-modal-title').textContent = 'Edit Card';
        document.getElementById('card-title').value = card.title;
        document.getElementById('card-url').value = card.url || '';
        document.getElementById('card-delete-btn').style.display = 'block';
        document.querySelectorAll('#size-selector .size-btn').forEach(b => b.classList.toggle('active', b.dataset.size === (card.size || '1x1')));
        document.getElementById('card-grid-col').value = card.grid_col || 1;
        document.getElementById('card-grid-row').value = card.grid_row || 1;
        const iconUrl = document.getElementById('card-icon-url');
        if (card.icon_path) {
            const iconSrc = Components.resolveIconUrl(card.icon_path);
            document.getElementById('icon-preview-img').src = iconSrc;
            document.getElementById('icon-upload-placeholder').style.display = 'none';
            document.getElementById('icon-upload-preview').style.display = 'block';
            if (iconUrl) iconUrl.value = card.icon_path.startsWith('http') ? card.icon_path : '';
        } else {
            document.getElementById('icon-upload-placeholder').style.display = 'flex';
            document.getElementById('icon-upload-preview').style.display = 'none';
            if (iconUrl) iconUrl.value = '';
        }
        Components.showModal('card-modal');
    }

    async _saveBlur() { try { const v = parseInt(document.getElementById('blur-slider').value); await api.updateSettings({ blur_radius: v }); this.settings.blur_radius = v; } catch (_) { console.error('[save-blur] failed', _); } }
    async _saveTheme(t) { try { await api.updateSettings({ dark_mode: t === 'dark' }); this.settings.dark_mode = t === 'dark'; } catch (_) { console.error('[save-theme] failed', _); } }

    _export() {
        const b = new Blob([JSON.stringify({ settings: this.settings, cards: this.cards, exportedAt: new Date().toISOString() }, null, 2)], { type: 'application/json' });
        const u = URL.createObjectURL(b); const a = document.createElement('a'); a.href = u; a.download = 'homepage-backup-' + new Date().toISOString().split('T')[0] + '.json'; a.click(); URL.revokeObjectURL(u);
        Components.showToast('Exported');
    }

    async _import(file) {
        if (!file) return;
        try {
            const d = JSON.parse(await file.text());
            if (!d.settings || !d.cards) throw new Error('Invalid');
            /* Use transactional import endpoint if available */
            await api.request('/import', { method: 'POST', body: JSON.stringify({ settings: d.settings, cards: d.cards }) });
            Components.showToast('Imported');
            await this.loadData();
        } catch (_) { Components.showToast('Import failed', 'error'); }
        document.getElementById('import-file-input').value = '';
    }
}

document.addEventListener('DOMContentLoaded', () => { window.App = new HomepageApp(); });
