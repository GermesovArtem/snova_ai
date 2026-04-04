const API_BASE = "/api/v1";

const getHeaders = () => {
    const token = localStorage.getItem('token');
    return {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    };
};

export const handleResponse = async (res: Response) => {
    const text = await res.text();
    if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${text}`);
    }
    try {
        return JSON.parse(text);
    } catch (e) {
        console.error("JSON Parse Error. Body was:", text);
        throw new Error("Server returned non-JSON response (likely HTML error page)");
    }
};

export const api = {
    async getMe() {
        const res = await fetch(`${API_BASE}/user/me`, { headers: getHeaders() });
        return handleResponse(res);
    },

    async updateModel(model: string) {
        const res = await fetch(`${API_BASE}/user/me/model`, {
            method: 'PUT',
            headers: getHeaders(),
            body: JSON.stringify({ model })
        });
        return handleResponse(res);
    },

    async generateEdit(prompt: string, imageUrls: string[] = []) {
        const res = await fetch(`${API_BASE}/generate/edit-url`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ prompt, image_urls: imageUrls })
        });
        return handleResponse(res);
    },

    async checkStatus(uuid: string) {
        const res = await fetch(`${API_BASE}/generations/${uuid}`, { headers: getHeaders() });
        return handleResponse(res);
    },

    async loginTelegram(data: any) {
        const res = await fetch(`${API_BASE}/auth/telegram`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return handleResponse(res);
    }
};
