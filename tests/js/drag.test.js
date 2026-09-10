import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { loadApp, loadIndexBody, loadScript } from './load.js';

loadScript('js/components.js');
loadScript('js/api.js');
loadApp();

function makeCard(overrides = {}) {
    return {
        id: 1,
        title: 'One',
        url: 'https://example.com',
        icon_path: null,
        size: '1x1',
        grid_col: 1,
        grid_row: 1,
        open_in_new_tab: true,
        ...overrides,
    };
}

async function makeApp(cards = []) {
    Object.assign(window.api, {
        getFullData: vi.fn(async () => ({
            settings: { background_image: null, blur_radius: 0, dark_mode: false },
            cards,
        })),
        getCards: vi.fn(async () => cards),
        updateCard: vi.fn(async () => ({})),
    });
    const app = new window.HomepageApp();
    await vi.waitFor(() => expect(app.settings).not.toBeNull());
    await new Promise(resolve => setTimeout(resolve, 10));
    return app;
}

describe('grid planning helpers', () => {
    let app;

    beforeEach(async () => {
        loadIndexBody();
        app = await makeApp();
        app.gridCols = 7;
    });

    it('plans a single move into a free cell', () => {
        app.cards = [makeCard()];
        expect(app._planMove(app.cards[0], 3, 2)).toEqual([{ id: 1, col: 3, row: 2 }]);
    });

    it('swaps cards instead of stacking them on a conflict', () => {
        app.cards = [
            makeCard({ id: 1, grid_col: 1, grid_row: 1 }),
            makeCard({ id: 2, grid_col: 2, grid_row: 1 }),
        ];

        const moves = app._planMove(app.cards[0], 2, 1);

        // Card 2 goes to the vacated cell, card 1 takes card 2's old cell.
        expect(moves).toEqual([
            { id: 2, col: 1, row: 1 },
            { id: 1, col: 2, row: 1 },
        ]);
    });

    it('never places a card past the last column', () => {
        app.cards = [
            makeCard({ id: 1, size: '2x2', grid_col: 6, grid_row: 1 }),
            makeCard({ id: 2, grid_col: 1, grid_row: 1 }),
        ];

        const [col, row] = app._findFreeSpot(app.cards[0], 7, 1, new Set());

        expect(col + 2 - 1).toBeLessThanOrEqual(app.gridCols);
        expect([col, row]).toEqual([6, 1]);
    });

    it('computes column from horizontal padding only and clamps to the grid', () => {
        const metrics = {
            gridRect: { left: 0, top: 0 },
            gap: 10,
            paddingLeft: 60,
            paddingTop: 5,
            cellH: 100,
            colWidth: 50,
            cols: 4,
        };

        expect(app._calcGridPos(110, 1000, metrics)).toEqual([1, 10]);
        expect(app._calcGridPos(10000, 10000, metrics)).toEqual([4, 91]);
    });

    it('spreads overlapping 2x2 cards without leaving gaps in the occupancy', () => {
        app.cards = [
            makeCard({ id: 1, size: '2x2', grid_col: 1, grid_row: 1 }),
            makeCard({ id: 2, size: '2x2', grid_col: 2, grid_row: 2 }),
        ];
        app._persistMoves = vi.fn();

        app._autoSpreadCards();

        const [a, b] = app.cards;
        const overlaps = !(a.grid_col + 2 <= b.grid_col || b.grid_col + 2 <= a.grid_col ||
            a.grid_row + 2 <= b.grid_row || b.grid_row + 2 <= a.grid_row);
        expect(overlaps).toBe(false);
        expect(app._persistMoves).toHaveBeenCalledWith([{ id: 2, col: 3, row: 1 }]);
    });
});

describe('drag & drop', () => {
    let app;
    let grid;
    let originalElementFromPoint;

    beforeEach(async () => {
        loadIndexBody();
        vi.stubGlobal('requestAnimationFrame', cb => { cb(); return 1; });
        vi.stubGlobal('cancelAnimationFrame', () => {});
        originalElementFromPoint = document.elementFromPoint;

        app = await makeApp();
        app.editMode = true;
        app.gridCols = 7;
        app.cards = [makeCard()];
        app.renderCards();

        grid = document.getElementById('cards-grid');
        grid.getBoundingClientRect = () => ({ left: 0, top: 0, width: 700, height: 160, right: 700, bottom: 160 });
        grid.setPointerCapture = vi.fn();
        const cell = grid.querySelector('.grid-cell[data-col="2"][data-row="1"]');
        document.elementFromPoint = vi.fn(() => cell);
    });

    afterEach(() => {
        document.elementFromPoint = originalElementFromPoint;
        vi.unstubAllGlobals();
    });

    function pointerEvent(type, clientX, clientY) {
        const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX, clientY });
        Object.defineProperty(event, 'pointerId', { value: 5 });
        return event;
    }

    it('moves the ghost with the pointer and persists the drop', async () => {
        const cardEl = grid.querySelector('.card');
        cardEl.dispatchEvent(pointerEvent('pointerdown', 100, 80));

        const ghost = document.querySelector('.drag-ghost');
        expect(ghost).not.toBeNull();
        expect(ghost.querySelector('.card-menu-btn')).toBeNull();
        expect(cardEl.classList.contains('drag-source')).toBe(true);

        grid.dispatchEvent(pointerEvent('pointermove', 180, 80));
        expect(ghost.style.transform).toContain('translate3d(80px, 0px');

        grid.dispatchEvent(pointerEvent('pointerup', 180, 80));

        await vi.waitFor(() => expect(window.api.updateCard).toHaveBeenCalledWith(1, { grid_col: 2, grid_row: 1 }));
        expect(document.querySelector('.drag-ghost')).toBeNull();
        expect(cardEl.classList.contains('drag-source')).toBe(false);
    });

    it('is not interruptible by the browser native drag', () => {
        const cardEl = grid.querySelector('.card');
        const dragStart = new Event('dragstart', { bubbles: true, cancelable: true });

        cardEl.dispatchEvent(dragStart);

        expect(dragStart.defaultPrevented).toBe(true);
    });

    it('keeps a click without movement a no-op', async () => {
        const cardEl = grid.querySelector('.card');
        cardEl.dispatchEvent(pointerEvent('pointerdown', 100, 80));
        grid.dispatchEvent(pointerEvent('pointerup', 100, 80));

        await new Promise(resolve => setTimeout(resolve, 10));
        expect(window.api.updateCard).not.toHaveBeenCalled();
        expect(document.querySelector('.drag-ghost')).toBeNull();
    });
});
