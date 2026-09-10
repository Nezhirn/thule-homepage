/**
 * UI Components for Homepage
 */

const Components = {
    _lastFocused: null,
    _toastTimer: null,

    /** Validate/pars a URL and return it only for safe schemes. */
    safeUrl(value) {
        if (!value) return null;
        try {
            const parsed = new URL(value, window.location.origin);
            if (!['http:', 'https:', 'mailto:'].includes(parsed.protocol)) return null;
            return parsed.href;
        } catch (_) {
            return null;
        }
    },

    /** Build a content signature; if unchanged between renders, the DOM node
     *  is reused (only grid position is updated), so <img> icons are not
     *  recreated and therefore not re-fetched by the browser. */
    _cardSignature(card, editMode) {
        return [
            card.id, card.title, card.url || '', card.icon_path || '',
            card.size || '1x1', card.open_in_new_tab === false ? 0 : 1,
            editMode ? 1 : 0,
        ].join('|');
    },

    /** Apply grid placement (cheap; safe to call every render). */
    _applyCardPosition(el, card) {
        const gCol = card.grid_col != null ? card.grid_col : 1;
        const gRow = card.grid_row != null ? card.grid_row : 1;
        const [cs, rs] = (card.size || '1x1').split('x').map(Number);
        el.style.gridRowStart = gRow;
        el.style.gridRowEnd = `span ${rs}`;
        el.style.gridColumnStart = gCol;
        el.style.gridColumnEnd = `span ${cs}`;
    },

    card(card, onEdit, onDelete, editMode) {
        /* Cards are real links so keyboard, middle-click and "open in new tab"
         * work; in edit mode a plain container is used instead. */
        const href = editMode ? null : Components.safeUrl(card.url);
        const el = document.createElement(href ? 'a' : 'div');
        el.className = 'card';
        el.dataset.id = card.id;
        el.dataset.size = card.size || '1x1';
        el.dataset.sig = Components._cardSignature(card, editMode);
        if (href) {
            el.href = href;
            if (card.open_in_new_tab !== false && !href.startsWith('mailto:')) {
                el.target = '_blank';
                el.rel = 'noopener noreferrer';
            }
        }

        /* explicit grid position from data */
        Components._applyCardPosition(el, card);

        if (editMode) {
            const mb = document.createElement('button');
            mb.className = 'card-menu-btn';
            mb.type = 'button';
            mb.setAttribute('aria-label', `Edit ${card.title || 'card'}`);
            mb.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg>';
            mb.title = 'Edit';
            mb.addEventListener('mousedown', e => e.stopPropagation());
            mb.addEventListener('click', e => {
                e.preventDefault(); e.stopPropagation();
                document.querySelectorAll('.card-dropdown').forEach(d => d.remove());
                const dd = el.querySelector('.card-dropdown');
                if (dd) { dd.remove(); return; }
                el.appendChild(Components._dropdown(card, onEdit, onDelete));
            });
            el.appendChild(mb);
        }

        const iconDiv = document.createElement('div');
        iconDiv.className = 'card-icon';
        if (card.icon_path) {
            const img = document.createElement('img');
            img.src = Components.resolveIconUrl(card.icon_path);
            img.alt = '';
            img.loading = 'lazy';
            img.decoding = 'async';
            img.draggable = false;
            img.onerror = () => { iconDiv.classList.add('default'); iconDiv.innerHTML = Components._defaultIcon(); };
            iconDiv.appendChild(img);
        } else {
            iconDiv.classList.add('default');
            iconDiv.innerHTML = Components._defaultIcon();
        }

        const title = document.createElement('span');
        title.className = 'card-title';
        title.textContent = card.title;
        el.appendChild(iconDiv);
        el.appendChild(title);

        return el;
    },

    _dropdown(card, onEdit, onDelete) {
        const dd = document.createElement('div');
        dd.className = 'card-dropdown';
        const eb = document.createElement('button');
        eb.type = 'button';
        eb.className = 'card-dropdown-item';
        eb.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg><span>Edit</span>';
        eb.addEventListener('click', e => { e.stopPropagation(); dd.remove(); onEdit(card); });
        const db = document.createElement('button');
        db.type = 'button';
        db.className = 'card-dropdown-item card-dropdown-item--danger';
        db.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg><span>Delete</span>';
        db.addEventListener('click', e => { e.stopPropagation(); dd.remove(); onDelete(card); });
        dd.appendChild(eb); dd.appendChild(db);
        return dd;
    },

    /** Resolve an icon_path to a display URL. Handles both external URLs and local uploads. */
    resolveIconUrl(icon_path) {
        if (!icon_path) return null;
        if (/^https?:\/\//i.test(icon_path)) return icon_path;
        return '/api/uploads/' + encodeURIComponent(icon_path);
    },

    _defaultIcon() {
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12l9-9 9 9"/><path d="M5 10v10h14V10"/></svg>';
    },

    /**
     * Reconciling renderer. Reuses existing card DOM nodes whose content
     * signature is unchanged (only repositioning them), so favicon <img>
     * elements are not recreated and the browser does not re-fetch them on
     * every render (resize, drag, edit-mode is the only full rebuild trigger).
     */
    renderCards(cards, container, onEdit, onDelete, editMode, cols = 7) {
        /* Empty state */
        if (cards.length === 0) {
            container.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg><p>No cards yet</p><span style="font-size:14px;opacity:0.7">Click the + button to add your first card</span></div>';
            return;
        }

        /* If a placeholder is present, clear it before reconciling */
        const placeholder = container.querySelector('.empty-state');
        if (placeholder) placeholder.remove();

        /* Close any open card menu — node reuse would otherwise leave it orphaned. */
        container.querySelectorAll('.card-dropdown').forEach(d => d.remove());

        /* Index existing card nodes by id */
        const existing = new Map();
        container.querySelectorAll(':scope > .card').forEach(el => {
            existing.set(el.dataset.id, el);
        });

        const keepIds = new Set();
        let newCount = 0;

        cards.forEach(c => {
            const id = String(c.id);
            keepIds.add(id);
            const sig = Components._cardSignature(c, editMode);
            const prev = existing.get(id);

            if (prev && prev.dataset.sig === sig) {
                /* Reuse node as-is; only refresh placement */
                Components._applyCardPosition(prev, c);
                prev.style.animationDelay = '';
            } else {
                /* Build (or rebuild) this card */
                const el = Components.card(c, onEdit, onDelete, editMode);
                el.style.animationDelay = (newCount++ * 50) + 'ms';
                if (prev) container.replaceChild(el, prev);
                else container.appendChild(el);
            }
        });

        /* Remove card nodes for cards that no longer exist */
        existing.forEach((el, id) => {
            if (!keepIds.has(id)) el.remove();
        });

        Components._renderGridCells(cards, container, editMode, cols);
    },

    /** Render/refresh the edit-mode grid-cell placeholder layer.
     *  Rebuilt only when its target geometry (editMode + maxRow + cols) changes. */
    _renderGridCells(cards, container, editMode, cols) {
        if (!editMode) {
            container.querySelectorAll(':scope > .grid-cell').forEach(c => c.remove());
            delete container.dataset.cellGeom;
            return;
        }

        const maxCol = cols;
        const maxRow = Math.max(...cards.map(c => {
            const gr = c.grid_row || 1;
            const [, ch] = (c.size || '1x1').split('x').map(Number);
            return gr + ch - 1;
        }), 3);

        const geom = `${maxCol}x${maxRow}`;
        if (container.dataset.cellGeom === geom &&
            container.querySelector(':scope > .grid-cell')) {
            return; // geometry unchanged — keep existing cells
        }

        container.querySelectorAll(':scope > .grid-cell').forEach(c => c.remove());
        const frag = document.createDocumentFragment();
        for (let r = 1; r <= maxRow; r++) {
            for (let c = 1; c <= maxCol; c++) {
                const cell = document.createElement('div');
                cell.className = 'grid-cell';
                cell.style.gridColumnStart = c;
                cell.style.gridColumnEnd = c + 1;
                cell.style.gridRowStart = r;
                cell.style.gridRowEnd = r + 1;
                cell.dataset.col = c;
                cell.dataset.row = r;
                frag.appendChild(cell);
            }
        }
        container.appendChild(frag);
        container.dataset.cellGeom = geom;
    },

    /** Render an error placeholder with a retry action. */
    renderErrorState(container, onRetry) {
        container.innerHTML = '';
        const wrap = document.createElement('div');
        wrap.className = 'empty-state';
        const message = document.createElement('p');
        message.textContent = 'Could not load data';
        const hint = document.createElement('span');
        hint.style.fontSize = '14px';
        hint.style.opacity = '0.7';
        hint.textContent = 'The server did not respond.';
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-secondary';
        button.style.marginTop = 'var(--space-md)';
        button.textContent = 'Retry';
        button.addEventListener('click', onRetry);
        wrap.append(message, hint, button);
        container.appendChild(wrap);
    },

    /** Render search suggestions without injecting untrusted text into HTML. */
    renderSuggestions(container, items, onSelect) {
        container.innerHTML = '';
        items.forEach(text => {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            item.setAttribute('role', 'option');
            const span = document.createElement('span');
            span.className = 'suggestion-text';
            span.textContent = text;
            item.appendChild(span);
            item.addEventListener('mousedown', e => e.preventDefault());
            item.addEventListener('click', () => onSelect(text));
            container.appendChild(item);
        });
    },

    updateBackground(imageUrl, blurRadius) {
        const bg = document.getElementById('background-image');
        if (!bg) return;
        if (imageUrl) {
            const safe = encodeURI(imageUrl).replace(/"/g, '%22');
            bg.style.backgroundImage = `url("${safe}")`;
            bg.style.opacity = '1';
        } else {
            bg.style.backgroundImage = 'none';
            bg.style.opacity = '0';
        }
        bg.style.filter = blurRadius > 0 ? `blur(${blurRadius}px)` : 'none';
    },

    _focusable(scope) {
        return Array.from(scope.querySelectorAll(
            'button, [href], input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])'
        )).filter(el => !el.disabled && (el.offsetParent !== null || el.getClientRects().length > 0));
    },

    showModal(id) {
        const modal = document.getElementById(id);
        if (!modal) return;
        Components._lastFocused = document.activeElement;
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
        const focusable = Components._focusable(modal);
        const preferred = focusable.find(el => el.matches(
            'input:not([type="range"]):not([type="file"]), textarea, select, [data-autofocus]'
        ));
        const target = preferred || focusable[0] || modal;
        if (target === modal) modal.tabIndex = -1;
        setTimeout(() => target.focus(), 50);
    },

    hideModal(id) {
        const modal = document.getElementById(id);
        if (!modal) return;
        modal.classList.remove('active');
        document.body.style.overflow = '';
        if (Components._lastFocused && Components._lastFocused.focus) {
            Components._lastFocused.focus();
        }
        Components._lastFocused = null;
    },

    showToast(msg, type = 'success') {
        const toast = document.getElementById('toast');
        const message = document.getElementById('toast-message');
        if (!toast || !message) return;
        toast.className = 'toast ' + type;
        message.textContent = msg;
        toast.classList.add('show');
        if (Components._toastTimer) clearTimeout(Components._toastTimer);
        Components._toastTimer = setTimeout(() => toast.classList.remove('show'), 3000);
    },

    setTheme(theme, persist = true) {
        document.documentElement.dataset.theme = theme;
        if (persist) {
            try { localStorage.setItem('theme', theme); } catch (_) { /* ignore */ }
        }
        document.getElementById('theme-light')?.classList.toggle('active', theme === 'light');
        document.getElementById('theme-dark')?.classList.toggle('active', theme === 'dark');
    },

    initFileUpload(area, inputId, onFile) {
        const input = document.getElementById(inputId);
        area.addEventListener('click', () => input.click());
        input.addEventListener('change', e => { if (e.target.files[0]) { onFile(e.target.files[0]); input.value = ''; } });
        area.addEventListener('dragover', e => { e.preventDefault(); area.style.borderColor = 'var(--accent)'; });
        area.addEventListener('dragleave', () => { area.style.borderColor = ''; });
        area.addEventListener('drop', e => { e.preventDefault(); area.style.borderColor = ''; if (e.dataTransfer.files[0] && e.dataTransfer.files[0].type.startsWith('image/')) onFile(e.dataTransfer.files[0]); });
    }
};

/* Keep keyboard focus inside an open modal. */
document.addEventListener('keydown', e => {
    if (e.key !== 'Tab') return;
    const modal = document.querySelector('.modal-overlay.active .modal');
    if (!modal) return;
    const focusable = Components._focusable(modal);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
    }
});

window.Components = Components;
