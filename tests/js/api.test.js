import { beforeEach, describe, expect, it, vi } from 'vitest';

import { loadScript, makeResponse } from './load.js';

loadScript('js/api.js');

const ApiClient = window.ApiClient;

describe('ApiClient.request', () => {
    beforeEach(() => {
        localStorage.clear();
        vi.unstubAllGlobals();
    });

    it('extracts string error details', async () => {
        vi.stubGlobal('fetch', vi.fn(async () => makeResponse(JSON.stringify({ detail: 'Bad request' }), 400)));

        await expect(new ApiClient('/api').request('/x')).rejects.toMatchObject({
            message: 'Bad request',
            status: 400,
        });
    });

    it('survives a non-JSON error body and keeps the status', async () => {
        vi.stubGlobal('fetch', vi.fn(async () => makeResponse('<html>Bad gateway</html>', 502)));

        await expect(new ApiClient('/api').request('/x')).rejects.toMatchObject({
            message: 'HTTP 502',
            status: 502,
        });
    });

    it('joins FastAPI validation detail arrays', async () => {
        const body = JSON.stringify({ detail: [{ msg: 'field required' }, { msg: 'invalid size' }] });
        vi.stubGlobal('fetch', vi.fn(async () => makeResponse(body, 422)));

        await expect(new ApiClient('/api').request('/x')).rejects.toMatchObject({
            message: 'field required; invalid size',
            status: 422,
        });
    });

    it('returns an empty object for 204', async () => {
        vi.stubGlobal('fetch', vi.fn(async () => makeResponse('', 204)));

        await expect(new ApiClient('/api').request('/x')).resolves.toEqual({});
    });

    it('aborts stalled requests with a timeout error', async () => {
        vi.stubGlobal('fetch', vi.fn((url, options) => new Promise((resolve, reject) => {
            options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
        })));

        await expect(new ApiClient('/api', 20).request('/slow')).rejects.toMatchObject({
            message: 'Request timed out',
            timeout: true,
        });
    });

    it('sends the stored auth token header', async () => {
        localStorage.setItem('authToken', 'secret');
        const fetchMock = vi.fn(async () => makeResponse('{}'));
        vi.stubGlobal('fetch', fetchMock);

        await new ApiClient('/api').request('/x');

        expect(fetchMock.mock.calls[0][1].headers['X-Auth-Token']).toBe('secret');
    });
});
