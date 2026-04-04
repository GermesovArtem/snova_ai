const API_BASE = "/api/v1";

const getHeaders = () => {
    const token = localStorage.getItem('token');
    return {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    };
};

export const api = {
    async getMe() {
        const res = await fetch(`${API_BASE}/user/me`, { headers: getHeaders() });
        return res.json();
    },

    async updateModel(model: string) {
        const res = await fetch(`${API_BASE}/user/me/model`, {
            method: 'PUT',
            headers: getHeaders(),
            body: JSON.stringify({ model })
        });
        return res.json();
    },

    async generateEdit(prompt: string, imageUrls: string[] = []) {
        const res = await fetch(`${API_BASE}/generate/edit-url`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ prompt, image_urls: imageUrls })
        });
        return res.json();
    },

    async checkStatus(uuid: string) {
        const res = await fetch(`${API_BASE}/generations/${uuid}`, { headers: getHeaders() });
        return res.json();
    },

    async loginTelegram(data: any) {
        const res = await fetch(`${API_BASE}/auth/telegram`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    }
};
