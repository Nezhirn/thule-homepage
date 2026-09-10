import { beforeEach, describe, expect, it, vi } from 'vitest';

import { loadScript } from './load.js';

loadScript('js/components.js');

const Components = window.Components;

describe('Components.safeUrl', () => {
    it('accepts http, https and mailto URLs', () => {
        expect(Components.safeUrl('https://example.com/page')).toBe('https://example.com/page');
        expect(Components.safeUrl('http://example.com')).toBe('http://example.com/');
        expect(Components.safeUrl('mailto:user@example.com')).toBe('mailto:user@example.com');
    });

    it('rejects dangerous schemes, including control-character obfuscation', () => {
        expect(Components.safeUrl('javascript:alert(1)')).toBeNull();
        expect(Components.safeUrl('java\tscript:alert(1)')).toBeNull();
        expect(Components.safeUrl('data:text/html,<script>alert(1)</script>')).toBeNull();
        expect(Components.safeUrl('vbscript:msgbox(1)')).toBeNull();
        expect(Components.safeUrl('')).toBeNull();
        expect(Components.safeUrl(null)).toBeNull();
    });
});

describe('Components.renderSuggestions', () => {
    it('never injects suggestion text as HTML or attributes', () => {
        const container = document.createElement('div');
        const hostile = 'foo" onmouseover=alert(1) x="';

        Components.renderSuggestions(container, [hostile], () => {});

        expect(container.querySelectorAll('.suggestion-item')).toHaveLength(1);
        expect(container.querySelector('.suggestion-item').hasAttribute('data-q')).toBe(false);
        expect(container.querySelector('.suggestion-text').textContent).toBe(hostile);
        expect(container.querySelector('[onmouseover]')).toBeNull();
        expect(container.querySelector('.suggestion-item').getAttributeNames()).toEqual(['class', 'role']);
    });

    it('invokes the callback with the selected text', () => {
        const container = document.createElement('div');
        const onSelect = vi.fn();
        Components.renderSuggestions(container, ['alpha', 'beta'], onSelect);

        container.querySelectorAll('.suggestion-item')[1].click();

        expect(onSelect).toHaveBeenCalledWith('beta');
    });
});

describe('Components.card accessibility', () => {
    const card = {
        id: 1, title: 'Example', url: 'https://example.com', icon_path: null,
        size: '1x1', grid_col: 1, grid_row: 1, open_in_new_tab: true,
    };

    it('renders a real link outside edit mode', () => {
        const el = Components.card(card, () => {}, () => {}, false);
        expect(el.tagName).toBe('A');
        expect(el.getAttribute('href')).toBe('https://example.com/');
        expect(el.getAttribute('target')).toBe('_blank');
        expect(el.getAttribute('rel')).toContain('noopener');
    });

    it('renders a container in edit mode and for unsafe URLs', () => {
        expect(Components.card(card, () => {}, () => {}, true).tagName).toBe('DIV');
        const unsafe = Components.card({ ...card, url: 'javascript:alert(1)' }, () => {}, () => {}, false);
        expect(unsafe.tagName).toBe('DIV');
        expect(unsafe.hasAttribute('href')).toBe(false);
    });
});

describe('Components.updateBackground', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="background-image"></div>';
    });

    it('quotes and encodes the image URL so it cannot inject CSS', () => {
        const hostile = 'x"); background-image: url(https://evil.example/log?';
        Components.updateBackground(hostile, 0);
        const value = document.getElementById('background-image').style.backgroundImage;
        expect(value.startsWith('url("')).toBe(true);
        expect(value).toContain('%22');
        expect(value).not.toContain('"); background');
    });
});
