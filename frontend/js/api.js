/**
 * API Client for Homepage Backend
 * Handles all HTTP requests to the FastAPI backend
 */

const API_BASE_URL = window.location.origin + '/api';
const API_TIMEOUT_MS = 10000;
const AUTH_TOKEN_KEY = 'authToken';

class ApiClient {
    constructor(baseUrl = API_BASE_URL, timeout = API_TIMEOUT_MS) {
        this.baseUrl = baseUrl;
        this.timeout = timeout;
    }

    getAuthToken() {
        try { return localStorage.getItem(AUTH_TOKEN_KEY); } catch (_) { return null; }
    }

    setAuthToken(token) {
        try {
            if (token) localStorage.setItem(AUTH_TOKEN_KEY, token);
            else localStorage.removeItem(AUTH_TOKEN_KEY);
        } catch (_) { /* storage unavailable */ }
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeout);

        const headers = { ...(options.headers || {}) };
        if (!(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }
        const token = this.getAuthToken();
        if (token) headers['X-Auth-Token'] = token;

        try {
            const response = await fetch(url, { ...options, headers, signal: controller.signal });

            const raw = await response.text();
            let data = {};
            if (raw) {
                try { data = JSON.parse(raw); } catch (_) { data = null; }
            }

            if (!response.ok) {
                const detail = data ? data.detail : null;
                let message;
                if (Array.isArray(detail)) {
                    message = detail.map(item => item.msg || JSON.stringify(item)).join('; ');
                } else if (typeof detail === 'string' && detail) {
                    message = detail;
                } else {
                    message = `HTTP ${response.status}`;
                }
                const error = new Error(message);
                error.status = response.status;
                throw error;
            }

            return data === null ? {} : data;
        } catch (error) {
            if (error.name === 'AbortError') {
                const timeoutError = new Error('Request timed out');
                timeoutError.status = 0;
                timeoutError.timeout = true;
                throw timeoutError;
            }
            throw error;
        } finally {
            clearTimeout(timer);
        }
    }

    // Settings
    async getSettings() {
        return this.request('/settings');
    }

    async updateSettings(settings) {
        return this.request('/settings', {
            method: 'PUT',
            body: JSON.stringify(settings),
        });
    }

    // Cards
    async getCards() {
        return this.request('/cards');
    }

    async createCard(card) {
        return this.request('/cards', {
            method: 'POST',
            body: JSON.stringify(card),
        });
    }

    async updateCard(cardId, card) {
        return this.request(`/cards/${cardId}`, {
            method: 'PUT',
            body: JSON.stringify(card),
        });
    }

    async deleteCard(cardId) {
        return this.request(`/cards/${cardId}`, {
            method: 'DELETE',
        });
    }

    async fetchIcon(url) {
        return this.request('/fetch-icon', {
            method: 'POST',
            body: JSON.stringify({ url }),
        });
    }

    // File Upload
    async uploadImage(file) {
        const formData = new FormData();
        formData.append('file', file);

        return this.request('/upload', {
            method: 'POST',
            body: formData,
        });
    }

    async deleteImage(filename) {
        return this.request(`/upload/${filename}`, {
            method: 'DELETE',
        });
    }

    // Full Data
    async getFullData() {
        return this.request('/full-data');
    }

    async importData(payload) {
        return this.request('/import', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    }
}

// Create global API instance
const api = new ApiClient();

// Export for use in other modules
window.ApiClient = ApiClient;
window.api = api;
