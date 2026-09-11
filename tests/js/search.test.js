import { beforeEach, describe, expect, it, vi } from 'vitest';

import { loadApp, loadIndexBody, loadScript } from './load.js';

loadScript('js/components.js');
loadScript('js/api.js');
loadApp();

function keydown(key) {
    const input = document.getElementById('search-input');
    const event = new window.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
    input.dispatchEvent(event);
    return event;
}

describe('search suggestions keyboard navigation (FE-19)', () => {
    let app;
    let input;
    let list;

    beforeEach(async () => {
        loadIndexBody();
        Object.assign(window.api, {
            getFullData: vi.fn(async () => ({
                settings: { background_image: null, blur_radius: 0, dark_mode: false },
                cards: [],
                cols: 7,
            })),
            getCards: vi.fn(async () => []),
        });
        app = new window.HomepageApp();
        await vi.waitFor(() => expect(app.settings).not.toBeNull());

        window.open = vi.fn();
        input = document.getElementById('search-input');
        list = document.getElementById('search-suggestions');

        /* Render a suggestion list the way the debounced fetch would. */
        window.Components.renderSuggestions(list, ['alpha', 'beta'], () => {});
        list.classList.add('show');
        app._sugIndex = -1;
    });

    it('moves the highlight down and up through the options', () => {
        keydown('ArrowDown');
        expect(app._sugIndex).toBe(0);
        expect(list.querySelectorAll('.suggestion-item')[0].getAttribute('aria-selected')).toBe('true');

        keydown('ArrowDown');
        expect(app._sugIndex).toBe(1);

        keydown('ArrowUp');
        expect(app._sugIndex).toBe(0);
    });

    it('wraps past the end back to the typed query', () => {
        keydown('ArrowDown');
        keydown('ArrowDown');
        keydown('ArrowDown');

        expect(app._sugIndex).toBe(-1);
        expect(list.querySelector('[aria-selected="true"]')).toBeNull();
        expect(input.hasAttribute('aria-activedescendant')).toBe(false);
    });

    it('searches for the highlighted suggestion on Enter', () => {
        input.value = 'al';
        keydown('ArrowDown');
        keydown('Enter');

        expect(input.value).toBe('alpha');
        expect(window.open).toHaveBeenCalledWith(
            expect.stringContaining('alpha'), '_blank', 'noopener,noreferrer',
        );
        expect(list.classList.contains('show')).toBe(false);
    });

    it('searches for the typed text when nothing is highlighted', () => {
        input.value = 'typed query';
        keydown('Enter');

        expect(window.open).toHaveBeenCalledWith(
            expect.stringContaining(encodeURIComponent('typed query')), '_blank', 'noopener,noreferrer',
        );
    });

    it('closes the list on Escape without searching', () => {
        input.value = 'alpha';
        keydown('ArrowDown');
        keydown('Escape');

        expect(list.classList.contains('show')).toBe(false);
        expect(input.getAttribute('aria-expanded')).toBe('false');
        expect(window.open).not.toHaveBeenCalled();
    });

    it('leaves arrow keys alone when the list is closed', () => {
        list.classList.remove('show');

        const event = keydown('ArrowDown');

        expect(event.defaultPrevented).toBe(false);
        expect(app._sugIndex).toBe(-1);
    });
});
