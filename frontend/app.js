// Vimeo Video Chatbot Frontend
class VimeoChatbot {
    constructor() {
        this.apiBaseUrl = 'http://127.0.0.1:8000';
        this.conversationId = this.generateConversationId();
        this.userId = this.getOrCreateUserId();
        this.isLoading = false;
        
        this.initializeElements();
        this.attachEventListeners();
        this.setWelcomeTime();
    }

    initializeElements() {
        this.chatContainer = document.getElementById('chatContainer');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.clearChatBtn = document.getElementById('clearChatBtn');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.errorModal = document.getElementById('errorModal');
        this.errorMessage = document.getElementById('errorMessage');
        this.closeErrorModal = document.getElementById('closeErrorModal');
        this.dismissError = document.getElementById('dismissError');
        this.charCount = document.getElementById('charCount');
    }

    attachEventListeners() {
        // Send message events
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
        this.messageInput.addEventListener('input', () => this.handleInputChange());

        // Clear chat
        this.clearChatBtn.addEventListener('click', () => this.clearChat());

        // Error modal
        this.closeErrorModal.addEventListener('click', () => this.hideErrorModal());
        this.dismissError.addEventListener('click', () => this.hideErrorModal());
        this.errorModal.addEventListener('click', (e) => {
            if (e.target === this.errorModal) this.hideErrorModal();
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => this.autoResizeTextarea());
    }

    generateConversationId() {
        return 'conv_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    getOrCreateUserId() {
        let userId = localStorage.getItem('vimeo_chatbot_user_id');
        if (!userId) {
            userId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('vimeo_chatbot_user_id', userId);
        }
        return userId;
    }

    setWelcomeTime() {
        const welcomeTimeElement = document.getElementById('welcomeTime');
        if (welcomeTimeElement) {
            welcomeTimeElement.textContent = this.formatTime(new Date());
        }
    }

    handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendMessage();
        }
    }

    handleInputChange() {
        const message = this.messageInput.value.trim();
        this.sendBtn.disabled = !message || this.isLoading;
        this.updateCharCount();
    }

    updateCharCount() {
        const count = this.messageInput.value.length;
        this.charCount.textContent = `${count}/2000`;
        
        // Change color if approaching limit
        if (count > 1800) {
            this.charCount.style.color = '#ef4444';
        } else if (count > 1500) {
            this.charCount.style.color = '#f59e0b';
        } else {
            this.charCount.style.color = '#9ca3af';
        }
    }

    autoResizeTextarea() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || this.isLoading) return;

        // Add user message to chat
        this.addMessageToChat(message, 'user');
        
        // Clear input and disable send button
        this.messageInput.value = '';
        this.updateCharCount();
        this.autoResizeTextarea();
        this.sendBtn.disabled = true;
        
        // Show loading
        this.showLoading();

        try {
            // Send request to backend
            const response = await this.sendChatRequest(message);
            
            // Add bot response to chat
            this.addMessageToChat(response.answer, 'bot', response.sources);
            
            // Update conversation ID if provided
            if (response.conversation_id) {
                this.conversationId = response.conversation_id;
            }

        } catch (error) {
            console.error('Error sending message:', error);
            this.showError('Failed to send message. Please try again.');
        } finally {
            this.hideLoading();
            this.sendBtn.disabled = false;
        }
    }

    async sendChatRequest(message) {
        const requestBody = {
            query: message,
            user_id: this.userId,
            conversation_id: this.conversationId,
            include_sources: true,
            top_k: 5
        };

        const response = await fetch(`${this.apiBaseUrl}/chat/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    }

    addMessageToChat(message, sender, sources = null) {
        const messageElement = this.createMessageElement(message, sender, sources);
        this.chatContainer.appendChild(messageElement);
        this.scrollToBottom();
    }

    createMessageElement(message, sender, sources = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = sender === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

        const content = document.createElement('div');
        content.className = 'message-content';

        const text = document.createElement('div');
        text.className = 'message-text';
        text.innerHTML = `<p>${this.escapeHtml(message)}</p>`;

        const time = document.createElement('div');
        time.className = 'message-time';
        time.innerHTML = `<span>${this.formatTime(new Date())}</span>`;

        content.appendChild(text);
        content.appendChild(time);

        // Add sources if available
        if (sources && sources.length > 0) {
            const sourcesDiv = this.createSourcesElement(sources);
            content.appendChild(sourcesDiv);
        }

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);

        return messageDiv;
    }

    createSourcesElement(sources) {
        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'sources';

        const header = document.createElement('h4');
        header.innerHTML = '<i class="fas fa-link"></i> Sources';
        sourcesDiv.appendChild(header);

        sources.forEach(source => {
            const sourceItem = document.createElement('div');
            sourceItem.className = 'source-item';

            const title = document.createElement('div');
            title.className = 'source-title';
            title.textContent = source.video_title || 'Unknown Video';

            const meta = document.createElement('div');
            meta.className = 'source-meta';
            const metaText = [];
            if (source.video_id) metaText.push(`Video ID: ${source.video_id}`);
            if (source.timestamp_start && source.timestamp_end) {
                metaText.push(`Time: ${this.formatTimestamp(source.timestamp_start)} - ${this.formatTimestamp(source.timestamp_end)}`);
            }
            if (source.relevance_score) {
                metaText.push(`Relevance: ${(source.relevance_score * 100).toFixed(1)}%`);
            }
            meta.textContent = metaText.join(' • ');

            sourceItem.appendChild(title);
            sourceItem.appendChild(meta);
            sourcesDiv.appendChild(sourceItem);
        });

        return sourcesDiv;
    }

    formatTimestamp(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    scrollToBottom() {
        setTimeout(() => {
            this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
        }, 100);
    }

    showLoading() {
        this.isLoading = true;
        this.loadingOverlay.classList.add('show');
    }

    hideLoading() {
        this.isLoading = false;
        this.loadingOverlay.classList.remove('show');
    }

    showError(message) {
        this.errorMessage.textContent = message;
        this.errorModal.classList.add('show');
    }

    hideErrorModal() {
        this.errorModal.classList.remove('show');
    }

    clearChat() {
        if (confirm('Are you sure you want to clear the chat history?')) {
            // Keep only the welcome message
            const welcomeMessage = this.chatContainer.querySelector('.bot-message');
            this.chatContainer.innerHTML = '';
            if (welcomeMessage) {
                this.chatContainer.appendChild(welcomeMessage);
            }
            
            // Generate new conversation ID
            this.conversationId = this.generateConversationId();
            
            // Scroll to top
            this.chatContainer.scrollTop = 0;
        }
    }

    // Health check method
    async checkBackendHealth() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/health`);
            if (response.ok) {
                console.log('Backend is healthy');
                return true;
            } else {
                console.warn('Backend health check failed');
                return false;
            }
        } catch (error) {
            console.error('Backend health check error:', error);
            return false;
        }
    }
}

// Initialize the chatbot when the page loads
document.addEventListener('DOMContentLoaded', () => {
    const chatbot = new VimeoChatbot();
    
    // Check backend health on load
    chatbot.checkBackendHealth().then(isHealthy => {
        if (!isHealthy) {
            chatbot.showError('Unable to connect to the backend server. Please make sure the server is running.');
        }
    });
    
    // Make chatbot globally available for debugging
    window.chatbot = chatbot;
});
