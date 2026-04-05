/**
 * API Client for Homepage Backend
 * Handles all HTTP requests to the FastAPI backend
 */

const API_BASE_URL = window.location.origin + '/api';

class ApiClient {
    constructor(baseUrl = API_BASE_URL) {
        this.baseUrl = baseUrl;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            ...options,
        };

        // Set headers if not already set
        if (!config.headers) {
            config.headers = {};
        }

        // Only set Content-Type for non-FormData requests
        if (!(options.body instanceof FormData)) {
            config.headers['Content-Type'] = 'application/json';
        }

        try {
            const response = await fetch(url, config);

            // Handle 204 No Content
            if (response.status === 204) {
                return {};
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Request failed');
            }

            return data;
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
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

    async reorderCards(data) {
        return this.request('/cards/reorder', {
            method: 'POST',
            body: JSON.stringify(data),
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

    // Health Check
    async healthCheck() {
        return this.request('/health');
    }
}

// Create global API instance
const api = new ApiClient();

// Export for use in other modules
window.ApiClient = ApiClient;
window.api = api;
