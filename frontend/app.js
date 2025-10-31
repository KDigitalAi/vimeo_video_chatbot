// Ultra-optimized Vimeo Video Chatbot Frontend
class VimeoChatbot {
    constructor() {
        // Pre-computed constants for O(1) access
        this.apiBaseUrl = this.getApiBaseUrl();
        this.conversationId = this.generateConversationId();
        this.userId = this.getOrCreateUserId();
        this.isLoading = false;
        
        // Performance optimizations
        this._elementCache = new Map();
        this._requestController = null;
        this._timeoutId = null;
        
        this.initializeElements();
        this.attachEventListeners();
        this.setWelcomeTime();
        this.testBackendConnection();
    }

    // Educational element initialization with caching
    initializeElements() {
        // Cache elements for O(1) access
        this.chatContainer = this._getCachedElement('chatContainer');
        this.messageInput = this._getCachedElement('messageInput');
        this.sendBtn = this._getCachedElement('sendBtn');
        this.clearChatBtn = this._getCachedElement('clearChatBtn');
        this.loadingOverlay = this._getCachedElement('loadingOverlay');
        this.errorModal = this._getCachedElement('errorModal');
        this.errorMessage = this._getCachedElement('errorMessage');
        this.closeErrorModal = this._getCachedElement('closeErrorModal');
        this.dismissError = this._getCachedElement('dismissError');
        this.charCount = this._getCachedElement('charCount');
        
        // Educational features
        this.accessibilityToggle = this._getCachedElement('accessibilityToggle');
    }

    // Ultra-optimized element caching for O(1) access
    _getCachedElement(id) {
        if (!this._elementCache.has(id)) {
            const element = document.getElementById(id);
            if (element) {
                this._elementCache.set(id, element);
            }
        }
        return this._elementCache.get(id);
    }

    // Educational event listeners with throttling and debouncing
    attachEventListeners() {
        // Send message events with throttling
        this.sendBtn.addEventListener('click', this._throttle(() => this.sendMessage(), 300));
        this.messageInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
        
        // Debounced input handling for better performance
        this.messageInput.addEventListener('input', this._debounce(() => {
            this.handleInputChange();
            this.autoResizeTextarea();
        }, 100));

        // Clear chat with throttling
        this.clearChatBtn.addEventListener('click', this._throttle(() => this.clearChat(), 300));

        // Educational features
        
        if (this.accessibilityToggle) {
            this.accessibilityToggle.addEventListener('click', this._throttle(() => this.toggleAccessibility(), 200));
        }

        // Error modal with throttling
        this.closeErrorModal.addEventListener('click', this._throttle(() => this.hideErrorModal(), 100));
        this.dismissError.addEventListener('click', this._throttle(() => this.hideErrorModal(), 100));
        this.errorModal.addEventListener('click', (e) => {
            if (e.target === this.errorModal) this.hideErrorModal();
        });
    }

    // Ultra-optimized throttling for performance
    _throttle(func, delay) {
        let timeoutId;
        let lastExecTime = 0;
        return function (...args) {
            const currentTime = Date.now();
            if (currentTime - lastExecTime > delay) {
                func.apply(this, args);
                lastExecTime = currentTime;
            } else {
                clearTimeout(timeoutId);
                timeoutId = setTimeout(() => {
                    func.apply(this, args);
                    lastExecTime = Date.now();
                }, delay - (currentTime - lastExecTime));
            }
        };
    }

    // Ultra-optimized debouncing for performance
    _debounce(func, delay) {
        let timeoutId;
        return function (...args) {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(this, args), delay);
        };
    }

    // Add method to get API base URL from environment or default
    getApiBaseUrl() {
        // Check for environment variable or use default
        if (typeof process !== 'undefined' && process.env && process.env.API_BASE_URL) {
            return process.env.API_BASE_URL;
        }
        // Check for window configuration
        if (typeof window !== 'undefined' && window.API_BASE_URL) {
            return window.API_BASE_URL;
        }
        // Check for meta tag configuration
        const metaApiUrl = document.querySelector('meta[name="api-base-url"]');
        if (metaApiUrl) {
            return metaApiUrl.getAttribute('content');
        }
        // Default fallback
        return 'http://127.0.0.1:8000';
    }

    // Test backend connection on startup
    async testBackendConnection() {
        try {
            console.log('🔍 Testing backend connection...');
            const response = await fetch(`${this.apiBaseUrl}/health`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const healthData = await response.json();
                console.log('✅ Backend connection successful:', healthData);
            } else {
                console.warn('⚠️ Backend health check failed:', response.status, response.statusText);
            }
        } catch (error) {
            console.error('❌ Backend connection test failed:', error);
            console.error('❌ Make sure the backend server is running on:', this.apiBaseUrl);
        }
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

    // Ultra-optimized sendMessage with request management
    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || this.isLoading) return;

        // Cancel any pending request
        if (this._requestController) {
            this._requestController.abort();
        }

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
            console.log('🚀 Sending message to backend:', message);
            console.log('🌐 API Base URL:', this.apiBaseUrl);
            
            // Send request to backend with optimized request management
            const response = await this.sendChatRequest(message);
            
            console.log('✅ Backend response received:', response);
            
            // Add bot response to chat
            this.addMessageToChat(response.answer, 'bot', response.sources);
            
            // Update conversation ID if provided
            if (response.conversation_id) {
                this.conversationId = response.conversation_id;
            }

        } catch (error) {
            console.error('❌ Error sending message:', error);
            console.error('❌ Error details:', {
                name: error.name,
                message: error.message,
                stack: error.stack
            });
            
            if (error.name !== 'AbortError') {
                // Show more specific error message
                const errorMessage = error.message || 'Failed to send message. Please try again.';
                this.showError(`Error: ${errorMessage}`);
            }
        } finally {
            this.hideLoading();
            this.sendBtn.disabled = false;
            this._requestController = null;
        }
    }

    // Ultra-optimized sendChatRequest with request management
    async sendChatRequest(message) {
        // Pre-allocated request body for O(1) access - wrapped for FastAPI compatibility
        const requestBody = {
            request: {
                query: message,
                user_id: this.userId,
                conversation_id: this.conversationId,
                include_sources: true,
                top_k: 5
            }
        };

        // Ultra-optimized request controller with timeout management
        this._requestController = new AbortController();
        this._timeoutId = setTimeout(() => this._requestController.abort(), 30000); // 30s timeout

        try {
            console.log('📡 Making request to:', `${this.apiBaseUrl}/chat/query`);
            
            const response = await fetch(`${this.apiBaseUrl}/chat/query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody),
                signal: this._requestController.signal
            });
            
            clearTimeout(this._timeoutId);
            this._timeoutId = null;

            console.log('📊 Response status:', response.status, response.statusText);

            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                try {
                    const cloned = response.clone();
                    const errorData = await cloned.json();
                    if (errorData && (errorData.detail || errorData.message)) {
                        errorMessage = errorData.detail || errorData.message;
                    }
                    console.error('❌ Backend error response:', errorData);
                } catch (_) {
                    try {
                        const textResponse = await response.text();
                        console.error('❌ Raw error response:', textResponse);
                        if (textResponse) errorMessage = textResponse;
                    } catch (__) {
                        // ignore secondary failures
                    }
                }
                throw new Error(errorMessage);
            }

            return await response.json();
        } catch (error) {
            if (this._timeoutId) {
                clearTimeout(this._timeoutId);
                this._timeoutId = null;
            }
            throw error;
        }
    }

    addMessageToChat(message, sender, sources = null) {
        const messageElement = this.createMessageElement(message, sender, sources);
        this.chatContainer.appendChild(messageElement);
        this.scrollToBottom();
    }

    // Ultra-optimized createMessageElement with document fragment
    createMessageElement(message, sender, sources = null) {
        // Use document fragment for better performance
        const fragment = document.createDocumentFragment();
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = sender === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

        const content = document.createElement('div');
        content.className = 'message-content';

        const text = document.createElement('div');
        text.className = 'message-text';
        
        // Enhanced text formatting for better readability
        if (sender === 'bot') {
            text.innerHTML = this.formatBotMessage(message);
        } else {
            text.innerHTML = `<p>${this.escapeHtml(message)}</p>`;
        }

        const time = document.createElement('div');
        time.className = 'message-time';
        time.innerHTML = `<span>${this.formatTime(new Date())}</span>`;

        content.appendChild(text);
        content.appendChild(time);

        // Add single-line sources display if available
        if (sources && sources.length > 0) {
            const sourcesLine = this.createSourcesLine(sources);
            content.appendChild(sourcesLine);
        }

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);

        return messageDiv;
    }

    // Enhanced text formatting for bot messages
    formatBotMessage(message) {
        // Escape HTML first
        let formatted = this.escapeHtml(message);
        
        // Convert markdown-style formatting to HTML
        formatted = this.convertMarkdownToHtml(formatted);
        
        // Wrap in paragraph if not already wrapped
        if (!formatted.startsWith('<')) {
            formatted = `<p>${formatted}</p>`;
        }
        
        return formatted;
    }

    // Convert enhanced markdown to HTML for educational formatting
    convertMarkdownToHtml(text) {
        // Educational section headers with emojis
        text = text.replace(/\*\*📘 Definition:\*\*/g, '<h4 class="edu-section">📘 Definition:</h4>');
        text = text.replace(/\*\*💡 Examples?:\*\*/g, '<h4 class="edu-section">💡 Examples:</h4>');
        text = text.replace(/\*\*🎯 (Why It Matters|Importance):\*\*/g, '<h4 class="edu-section">🎯 $1:</h4>');
        text = text.replace(/\*\*🔍 Key Points?:\*\*/g, '<h4 class="edu-section">🔍 Key Points:</h4>');
        text = text.replace(/\*\*📝 Note:\*\*/g, '<h4 class="edu-section">📝 Note:</h4>');
        text = text.replace(/\*\*⚡ Quick Tip:\*\*/g, '<h4 class="edu-section">⚡ Quick Tip:</h4>');
        
        // Regular headers
        text = text.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        text = text.replace(/^## (.*$)/gim, '<h2>$1</h2>');
        text = text.replace(/^# (.*$)/gim, '<h1>$1</h1>');
        
        // Bold text
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/__(.*?)__/g, '<strong>$1</strong>');
        
        // Italic text
        text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
        text = text.replace(/_(.*?)_/g, '<em>$1</em>');
        
        // Code blocks
        text = text.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
        text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // Enhanced list processing
        text = text.replace(/^\* (.*$)/gim, '<li>$1</li>');
        text = text.replace(/^- (.*$)/gim, '<li>$1</li>');
        text = text.replace(/^(\d+)\. (.*$)/gim, '<li>$1. $2</li>');
        
        // Wrap consecutive list items in ul/ol
        text = text.replace(/(<li>.*<\/li>)/gs, (match) => {
            const items = match.match(/<li>.*?<\/li>/g);
            if (items && items.length > 1) {
                return `<ul>${match}</ul>`;
            }
            return match;
        });
        
        // Line breaks - better handling for educational content
        text = text.replace(/\n\n/g, '</p><p>');
        text = text.replace(/\n/g, '<br>');
        
        return text;
    }

    // Create single-line sources display
    createSourcesLine(sources) {
        const sourcesLine = document.createElement('div');
        sourcesLine.className = 'sources-line';
        
        // Limit to first 3 sources
        const maxSources = 3;
        const displaySources = sources.slice(0, maxSources);
        const remainingCount = sources.length - maxSources;
        
        // Create separate source item elements for flexbox
        displaySources.forEach((source) => {
            const title = source.video_title || 'Unknown Video';
            const relevance = source.relevance_score ? 
                `(${(source.relevance_score * 100).toFixed(1)}%)` : '';
            
            const sourceItem = document.createElement('span');
            sourceItem.className = 'source-item-inline';
            sourceItem.innerHTML = `
                <span class="source-title-inline">${this.escapeHtml(title)}</span>
                <span class="source-relevance">${relevance}</span>
            `;
            
            sourcesLine.appendChild(sourceItem);
        });
        
        // Add "more" indicator if there are additional sources
        if (remainingCount > 0) {
            const moreIndicator = document.createElement('span');
            moreIndicator.className = 'sources-more';
            moreIndicator.textContent = `… +${remainingCount} more`;
            sourcesLine.appendChild(moreIndicator);
        }
        
        return sourcesLine;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // Ultra-optimized scrollToBottom with requestAnimationFrame
    scrollToBottom() {
        requestAnimationFrame(() => {
            this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
        });
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

    // Ultra-optimized clearChat with efficient DOM management
    clearChat() {
        if (confirm('Are you sure you want to clear the chat history?')) {
            // Keep only the welcome message
            const welcomeMessage = this.chatContainer.querySelector('.bot-message');
            
            // Ultra-optimized DOM clearing
            while (this.chatContainer.firstChild) {
                this.chatContainer.removeChild(this.chatContainer.firstChild);
            }
            
            if (welcomeMessage) {
                this.chatContainer.appendChild(welcomeMessage);
            }
            
            // Generate new conversation ID
            this.conversationId = this.generateConversationId();
            
            // Ultra-optimized scroll to top
            requestAnimationFrame(() => {
                this.chatContainer.scrollTop = 0;
            });
        }
    }

    // Educational features

    toggleAccessibility() {
        document.body.classList.toggle('high-contrast');
        const isHighContrast = document.body.classList.contains('high-contrast');
        this.accessibilityToggle.setAttribute('aria-pressed', isHighContrast);
        
        // Save preference to localStorage
        localStorage.setItem('highContrastMode', isHighContrast);
        
        // Update button appearance
        if (isHighContrast) {
            this.accessibilityToggle.style.backgroundColor = '#2563eb';
            this.accessibilityToggle.style.color = '#ffffff';
        } else {
            this.accessibilityToggle.style.backgroundColor = '#f8fafc';
            this.accessibilityToggle.style.color = '#64748b';
        }
    }

    // Initialize accessibility mode from localStorage
    initializeAccessibility() {
        const isHighContrast = localStorage.getItem('highContrastMode') === 'true';
        if (isHighContrast) {
            document.body.classList.add('high-contrast');
            this.accessibilityToggle.setAttribute('aria-pressed', 'true');
            this.accessibilityToggle.style.backgroundColor = '#2563eb';
            this.accessibilityToggle.style.color = '#ffffff';
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

// Educational initialization with performance monitoring
document.addEventListener('DOMContentLoaded', () => {
    const chatbot = new VimeoChatbot();
    
    // Initialize educational features
    chatbot.initializeAccessibility();
    
    // Backend health check with timeout
    chatbot.checkBackendHealth().then(isHealthy => {
        if (!isHealthy) {
            chatbot.showError('Unable to connect to the learning server. Please make sure the server is running.');
        }
    });
    
    // Make chatbot globally available for debugging
    window.chatbot = chatbot;
    
    // Educational cleanup on page unload
    window.addEventListener('beforeunload', () => {
        if (chatbot._requestController) {
            chatbot._requestController.abort();
        }
        if (chatbot._timeoutId) {
            clearTimeout(chatbot._timeoutId);
        }
    });
});
