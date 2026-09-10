import { beforeEach, describe, expect, it, vi } from 'vitest';

import { loadApp, loadIndexBody, loadScript } from './load.js';

loadScript('js/components.js');
loadScript('js/api.js');
loadApp();

const card = {
    id: 7,
    title: 'Card',
    url: 'https://example.com',
    icon_path: 'icon.png',
    size: '2x2',
    grid_col: 1,
    grid_row: 1,
    open_in_new_tab: true,
};

describe('card modal state', () => {
    let app;

    beforeEach(async () => {
        loadIndexBody();
        Object.assign(window.api, {
            getFullData: vi.fn(async () => ({
                settings: { background_image: null, blur_radius: 0, dark_mode: false },
                cards: [],
            })),
            getCards: vi.fn(async () => []),
            updateCard: vi.fn(async () => ({})),
            createCard: vi.fn(async () => ({})),
            updateSettings: vi.fn(async () => ({})),
            deleteCard: vi.fn(async () => ({})),
        });
        app = new window.HomepageApp();
        await vi.waitFor(() => expect(app.settings).not.toBeNull());
    });

    it('editing a card preserves its size and icon (review C6)', async () => {
        app._editCard(card);
        expect(document.querySelector('#size-selector .size-btn.active').dataset.size).toBe('2x2');
        expect(document.getElementById('icon-upload-preview').style.display).toBe('block');

        document.getElementById('card-title').value = 'Renamed';
        document.getElementById('card-save-btn').click();

        await vi.waitFor(() => expect(window.api.updateCard).toHaveBeenCalled());
        const [id, payload] = window.api.updateCard.mock.calls[0];
        expect(id).toBe(7);
        expect(payload.title).toBe('Renamed');
        expect(payload.size).toBe('2x2');
        expect(payload.icon_path).toBe('icon.png');
    });

    it('does not leak the edited icon into a newly created card', async () => {
        app._editCard(card);
        app._resetCardModal();
        document.getElementById('card-title').value = 'New card';
        document.getElementById('card-save-btn').click();

        await vi.waitFor(() => expect(window.api.createCard).toHaveBeenCalled());
        const payload = window.api.createCard.mock.calls[0][0];
        expect(payload.icon_path).toBeNull();
        expect(payload.size).toBe('1x1');
    });

    it('the remove button clears the icon for the next save', async () => {
        app._editCard(card);
        document.getElementById('icon-remove-btn').click();
        document.getElementById('card-save-btn').click();

        await vi.waitFor(() => expect(window.api.updateCard).toHaveBeenCalled());
        expect(window.api.updateCard.mock.calls[0][1].icon_path).toBeNull();
    });

    it('accepts a typed icon URL', async () => {
        app._editCard({ ...card, icon_path: null });
        const input = document.getElementById('card-icon-url');
        input.value = 'https://cdn.example.com/icon.png';
        input.dispatchEvent(new Event('input'));
        document.getElementById('card-save-btn').click();

        await vi.waitFor(() => expect(window.api.updateCard).toHaveBeenCalled());
        expect(window.api.updateCard.mock.calls[0][1].icon_path).toBe('https://cdn.example.com/icon.png');
    });

    it('reverts the theme when the server write fails (review M21)', async () => {
        app.settings = { background_image: null, blur_radius: 0, dark_mode: false };
        window.api.updateSettings = vi.fn(async () => { throw new Error('offline'); });
        window.Components.setTheme('dark');

        await app._saveTheme('dark');

        expect(document.documentElement.dataset.theme).toBe('light');
        expect(localStorage.getItem('theme')).toBe('light');
    });
});
