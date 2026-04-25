const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

class APIClient {
    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_URL}/books/upload`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`Upload failed: ${response.statusText}`);
        }

        return await response.json();
    }

    async query(messages, query, topK = 5) {
        const response = await fetch(`${API_URL}/chat/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                messages,
                query,
                top_k: topK,
            }),
        });

        if (!response.ok) {
            throw new Error(`Query failed: ${response.statusText}`);
        }

        return await response.json();
    }

    async getHealth() {
        const response = await fetch(`${API_URL}/chat/health`);
        return await response.json();
    }
}

class ChatUI {
    constructor() {
        this.api = new APIClient();
        this.messages = [];
        this.currentSources = [];
        this.initializeElements();
        this.attachEventListeners();
        this.checkApiHealth();
    }

    initializeElements() {
        this.dropZone = document.getElementById('dropZone');
        this.fileInput = document.getElementById('fileInput');
        this.uploadProgress = document.getElementById('uploadProgress');
        this.uploadedFiles = document.getElementById('uploadedFiles');
        this.chatMessages = document.getElementById('chatMessages');
        this.queryInput = document.getElementById('queryInput');
        this.chatForm = document.getElementById('chatForm');
        this.sendButton = document.getElementById('sendButton');
        this.sourcesList = document.getElementById('sourcesList');
        this.progressFill = document.getElementById('progressFill');
        this.progressText = document.getElementById('progressText');
    }

    attachEventListeners() {
        // File upload
        this.dropZone.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e.target.files));

        // Drag and drop
        this.dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.dropZone.classList.add('dragover');
        });

        this.dropZone.addEventListener('dragleave', () => {
            this.dropZone.classList.remove('dragover');
        });

        this.dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            this.dropZone.classList.remove('dragover');
            this.handleFileSelect(e.dataTransfer.files);
        });

        // Chat
        this.chatForm.addEventListener('submit', (e) => this.handleQuery(e));
    }

    async checkApiHealth() {
        try {
            await this.api.getHealth();
        } catch (error) {
            this.addSystemMessage('⚠️ Backend is unavailable. Please check your connection.');
        }
    }

    handleFileSelect(files) {
        Array.from(files).forEach((file) => this.uploadFile(file));
    }

    async uploadFile(file) {
        if (!file.name.endsWith('.pdf')) {
            this.addFileError(`${file.name}: Only PDF files are supported`);
            return;
        }

        this.showUploadProgress();

        try {
            const result = await this.api.uploadFile(file);
            this.addFileSuccess(`${file.name} uploaded - indexing in progress`);
            this.addSystemMessage(`📄 ${file.name} queued for indexing`);
        } catch (error) {
            this.addFileError(`${file.name}: ${error.message}`);
        } finally {
            this.hideUploadProgress();
        }
    }

    showUploadProgress() {
        this.uploadProgress.style.display = 'block';
        this.progressFill.style.width = '0%';
    }

    hideUploadProgress() {
        setTimeout(() => {
            this.uploadProgress.style.display = 'none';
        }, 1500);
    }

    addFileSuccess(text) {
        const div = document.createElement('div');
        div.className = 'file-item success';
        div.innerHTML = `<span>✓ ${text}</span>`;
        this.uploadedFiles.appendChild(div);
    }

    addFileError(text) {
        const div = document.createElement('div');
        div.className = 'file-item error';
        div.innerHTML = `<span>✗ ${text}</span>`;
        this.uploadedFiles.appendChild(div);
    }

    async handleQuery(e) {
        e.preventDefault();

        const query = this.queryInput.value.trim();
        if (!query) return;

        this.queryInput.value = '';
        this.sendButton.disabled = true;

        this.addUserMessage(query);

        try {
            const response = await this.api.query(this.messages, query);

            this.messages.push({ role: 'user', content: query });
            this.messages.push({ role: 'assistant', content: response.answer });

            this.addAssistantMessage(response.answer);
            this.displaySources(response.sources);

            // Add timing info
            const totalTime = (response.retrieval_time_ms + response.generation_time_ms) / 1000;
            this.addSystemMessage(`⏱️ Response generated in ${totalTime.toFixed(2)}s`);

        } catch (error) {
            this.addSystemMessage(`❌ Error: ${error.message}`);
        } finally {
            this.sendButton.disabled = false;
            this.queryInput.focus();
        }
    }

    addUserMessage(content) {
        const div = document.createElement('div');
        div.className = 'message user';
        div.innerHTML = `<p>${this.escapeHtml(content)}</p>`;
        this.chatMessages.appendChild(div);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    addAssistantMessage(content) {
        const div = document.createElement('div');
        div.className = 'message assistant';
        div.innerHTML = `<p>${this.escapeHtml(content)}</p>`;
        this.chatMessages.appendChild(div);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    addSystemMessage(content) {
        const div = document.createElement('div');
        div.className = 'message system';
        div.innerHTML = `<p>${content}</p>`;
        this.chatMessages.appendChild(div);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    displaySources(sources) {
        if (!sources || sources.length === 0) {
            this.sourcesList.innerHTML = '<p class="no-sources">No sources found</p>';
            return;
        }

        this.sourcesList.innerHTML = '';

        sources.forEach((source) => {
            const div = document.createElement('div');
            div.className = 'source-item';

            const relevance = (source.relevance_score * 100).toFixed(0);
            let pageInfo = '';
            if (source.page_number) {
                pageInfo = `<p>📄 Page ${source.page_number}</p>`;
            }

            div.innerHTML = `
                <p><strong>${source.filename}</strong></p>
                ${pageInfo}
                <p>Relevance: ${relevance}%</p>
            `;

            this.sourcesList.appendChild(div);
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize UI when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new ChatUI();
});
