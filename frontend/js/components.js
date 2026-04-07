/**
 * UI Components for Homepage
 */

const Components = {

    card(card, onEdit, editMode, cols) {
        const el = document.createElement('div');
        el.className = 'card';
        el.dataset.id = card.id;
        el.dataset.size = card.size || '1x1';

        /* explicit grid position from data */
        const gCol = card.grid_col != null ? card.grid_col : 1;
        const gRow = card.grid_row != null ? card.grid_row : 1;
        const [cs, rs] = (card.size || '1x1').split('x').map(Number);
        el.style.gridRowStart = gRow;
        el.style.gridRowEnd = `span ${rs}`;
        el.style.gridColumnStart = gCol;
        el.style.gridColumnEnd = `span ${cs}`;

        if (editMode) {
            const mb = document.createElement('button');
            mb.className = 'card-menu-btn';
            mb.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg>';
            mb.title = 'Edit';
            mb.addEventListener('mousedown', e => e.stopPropagation());
            mb.addEventListener('click', e => {
                e.preventDefault(); e.stopPropagation();
                document.querySelectorAll('.card-dropdown').forEach(d => d.remove());
                let dd = el.querySelector('.card-dropdown');
                if (dd) { dd.remove(); return; }
                el.appendChild(Components._dropdown(card, onEdit));
            });
            el.appendChild(mb);
        }

        const iconDiv = document.createElement('div');
        iconDiv.className = 'card-icon';
        if (card.icon_path) {
            const img = document.createElement('img');
            img.src = Components.resolveIconUrl(card.icon_path);
            img.alt = card.title;
            img.loading = 'lazy';
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

        if (card.url && !editMode) {
            el.style.cursor = 'pointer';
            el.addEventListener('click', () => window.open(card.url, '_blank', 'noopener,noreferrer'));
        }

        return el;
    },

    _dropdown(card, onEdit) {
        const dd = document.createElement('div');
        dd.className = 'card-dropdown';
        const eb = document.createElement('button');
        eb.className = 'card-dropdown-item';
        eb.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg><span>Edit</span>';
        eb.addEventListener('click', e => { e.stopPropagation(); dd.remove(); onEdit(card); });
        const db = document.createElement('button');
        db.className = 'card-dropdown-item card-dropdown-item--danger';
        db.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg><span>Delete</span>';
        db.addEventListener('click', async e => {
            e.stopPropagation(); dd.remove();
            if (confirm('Delete this card?')) {
                try {
                    await api.deleteCard(card.id);
                    if (window.App) await window.App.loadCards();
                    Components.showToast('Card deleted');
                } catch (_) { Components.showToast('Failed to delete', 'error'); }
            }
        });
        dd.appendChild(eb); dd.appendChild(db);
        return dd;
    },

    /** Resolve an icon_path to a display URL. Handles both external URLs and local uploads. */
    resolveIconUrl(icon_path) {
        if (!icon_path) return null;
        return icon_path.startsWith('http') ? icon_path : '/api/uploads/' + icon_path;
    },

    _defaultIcon() {
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12l9-9 9 9"/><path d="M5 10v10h14V10"/></svg>';
    },

    renderCards(cards, container, onEdit, editMode, cols = 7) {
        container.innerHTML = '';
        if (cards.length === 0) {
            container.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg><p>No cards yet</p><span style="font-size:14px;opacity:0.7">Click the + button to add your first card</span></div>';
            return;
        }
        cards.forEach((c, i) => {
            const el = Components.card(c, onEdit, editMode, cols);
            el.style.animationDelay = (i * 50) + 'ms';
            container.appendChild(el);
        });

        /* Render grid cell placeholders in edit mode — ALL visible cells */
        if (editMode) {
            const maxCol = cols;
            const maxRow = Math.max(...cards.map(c => {
                const gr = c.grid_row || 1;
                const [, ch] = (c.size || '1x1').split('x').map(Number);
                return gr + ch - 1;
            }), 3);

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
                    container.appendChild(cell);
                }
            }
        }
    },

    updateBackground(imageUrl, blurRadius) {
        const bg = document.getElementById('background-image');
        if (imageUrl) { bg.style.backgroundImage = 'url(' + imageUrl + ')'; bg.style.opacity = '1'; }
        else { bg.style.backgroundImage = 'none'; bg.style.opacity = '0'; }
        const blur = blurRadius > 0 ? 'blur(' + blurRadius + 'px)' : 'none';
        bg.style.filter = blur;
    },

    showModal(id) {
        const m = document.getElementById(id);
        if (m) { m.classList.add('active'); document.body.style.overflow = 'hidden'; const inp = m.querySelector('input:not([type=hidden])'); if (inp) setTimeout(() => inp.focus(), 100); }
    },

    hideModal(id) {
        const m = document.getElementById(id);
        if (m) { m.classList.remove('active'); document.body.style.overflow = ''; }
    },

    showToast(msg, type = 'success') {
        const t = document.getElementById('toast');
        const tm = document.getElementById('toast-message');
        t.className = 'toast ' + type;
        tm.textContent = msg;
        t.classList.add('show');
        setTimeout(() => t.classList.remove('show'), 3000);
    },

    setTheme(theme) {
        document.documentElement.dataset.theme = theme;
        localStorage.setItem('theme', theme);
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

window.Components = Components;
