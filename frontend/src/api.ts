const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

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
        throw new Error("Server returned non-JSON response");
    }
};

export const api = {
    async getMe() {
        const res = await fetch(`${API_BASE}/user/me`, { headers: getHeaders() });
        return handleResponse(res);
    },

    async getConfigModels() {
        const res = await fetch(`${API_BASE}/config/models`, { headers: getHeaders() });
        return handleResponse(res);
    },

    async updateModel(model: string) {
        const res = await fetch(`${API_BASE}/user/model`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ model_id: model })
        });
        return handleResponse(res);
    },

    async generateEdit(prompt: string, images: File[] = [], model_id?: string, aspect_ratio?: string, output_format?: string, status_message_id?: number, s3_url?: string) {
        const formData = new FormData();
        formData.append('prompt', prompt);
        if (model_id) formData.append('model_id', model_id);
        if (aspect_ratio) formData.append('aspect_ratio', aspect_ratio);
        if (output_format) formData.append('output_format', output_format);
        if (status_message_id) formData.append('status_message_id', status_message_id.toString());
        if (s3_url) formData.append('s3_url', s3_url);
        images.forEach(img => formData.append('images', img));

        const token = localStorage.getItem('token');
        const res = await fetch(`${API_BASE}/generate/edit`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
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
    },

    async getHistory() {
        const res = await fetch(`${API_BASE}/user/history`, { headers: getHeaders() });
        return handleResponse(res);
    },

    async createPayment(packId: string) {
        const res = await fetch(`${API_BASE}/payments/create?pack_id=${packId}`, {
            method: 'POST',
            headers: getHeaders()
        });
        return handleResponse(res);
    },

    // --- Admin Panel Methods ---
    async adminLogin(username: string, password: string) {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        
        const res = await fetch(`${API_BASE}/admin/token`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });
        return handleResponse(res);
    },

    async getAdminStats() {
        const res = await fetch(`${API_BASE}/admin/stats`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('admin_token')}` }
        });
        return handleResponse(res);
    },

    async adminListUsers() {
        const res = await fetch(`${API_BASE}/admin/users`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('admin_token')}` }
        });
        return handleResponse(res);
    },

    async adminUpdateBalance(userId: number, amount: number) {
        const res = await fetch(`${API_BASE}/admin/users/${userId}/balance`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('admin_token')}` 
            },
            body: JSON.stringify({ amount })
        });
        return handleResponse(res);
    },

    async adminBroadcast(text: string) {
        const res = await fetch(`${API_BASE}/admin/broadcast`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('admin_token')}` 
            },
            body: JSON.stringify({ text })
        });
        return handleResponse(res);
    },

    async getMessages() {
        const res = await fetch(`${API_BASE}/user/messages`, { headers: getHeaders() });
        return handleResponse(res);
    },

    async getActiveTasks() {
        const res = await fetch(`${API_BASE}/user/active-tasks`, { headers: getHeaders() });
        return handleResponse(res);
    },

    async saveMessage(role: string, text?: string, imageUrl?: string, meta?: any) {
        const res = await fetch(`${API_BASE}/user/messages`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}` 
            },
            body: JSON.stringify({ role, text, image_url: imageUrl, meta })
        });
        return handleResponse(res);
    },

    async updateMessage(msgId: number, text?: string, meta?: any) {
        const res = await fetch(`${API_BASE}/user/messages/${msgId}`, {
            method: 'PATCH',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}` 
            },
            body: JSON.stringify({ text, meta })
        });
        if (res.status === 404) return { success: true }; // Silent ignore if already deleted or lost
        return handleResponse(res);
    },

    async deleteMessage(msgId: number) {
        const res = await fetch(`${API_BASE}/user/messages/${msgId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (res.status === 404) return { success: true }; // Silent ignore
        return handleResponse(res);
    },

    async uploadImage(file: File) {
        const formData = new FormData();
        formData.append('image', file);
        const res = await fetch(`${API_BASE}/user/upload`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
            body: formData
        });
        return handleResponse(res);
    }
};
