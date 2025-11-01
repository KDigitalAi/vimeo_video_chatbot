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
        this.historyBtn = this._getCachedElement('historyBtn');
        this.newChatBtn = this._getCachedElement('newChatBtn');
        this.loadingOverlay = this._getCachedElement('loadingOverlay');
        this.errorModal = this._getCachedElement('errorModal');
        this.errorMessage = this._getCachedElement('errorMessage');
        this.closeErrorModal = this._getCachedElement('closeErrorModal');
        this.dismissError = this._getCachedElement('dismissError');
        this.charCount = this._getCachedElement('charCount');
        
        // Chat history elements
        this.historySidebar = this._getCachedElement('chatHistorySidebar');
        this.toggleHistoryBtn = this._getCachedElement('toggleHistoryBtn');
        this.historyContent = this._getCachedElement('historyContent');
        this.historyLoading = this._getCachedElement('historyLoading');
        this.historyEmpty = this._getCachedElement('historyEmpty');
        this.historyList = this._getCachedElement('historyList');
        
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

        // New chat with throttling
        if (this.newChatBtn) {
            this.newChatBtn.addEventListener('click', this._throttle(() => this.newChat(), 300));
        }

        // Chat history with throttling
        if (this.historyBtn) {
            this.historyBtn.addEventListener('click', this._throttle(() => this.toggleHistorySidebar(), 300));
        }
        if (this.toggleHistoryBtn) {
            this.toggleHistoryBtn.addEventListener('click', this._throttle(() => this.toggleHistorySidebar(), 300));
        }

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
            this.charCount.style.color = '#E91E63';
        } else if (count > 1500) {
            this.charCount.style.color = '#F48FB1';
        } else {
            this.charCount.style.color = '#212121';
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

            // Save conversation locally and refresh history
            this.saveConversationToLocal(message, response.answer);
            this.refreshChatHistory();

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
        if (sender === 'user') {
            avatar.innerHTML = '<i class="fas fa-user"></i>';
        } else {
            // Use custom logo image instead of robot icon
            avatar.innerHTML = '<img src="logo.png" alt="Chatbot" class="bot-avatar-img">';
        }

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

    // Start a new chat conversation
    newChat() {
        // Find the original welcome message if it exists
        let welcomeMessage = null;
        const messages = this.chatContainer.querySelectorAll('.message');
        for (const msg of messages) {
            if (msg.classList.contains('bot-message')) {
                const textContent = msg.textContent || '';
                if (textContent.includes('Welcome to your Learning Assistant') || 
                    textContent.includes('what would you like to know today')) {
                    welcomeMessage = msg.cloneNode(true);
                    break;
                }
            }
        }
        
        // Ultra-optimized DOM clearing
        while (this.chatContainer.firstChild) {
            this.chatContainer.removeChild(this.chatContainer.firstChild);
        }
        
        // If no welcome message found, recreate it from the original HTML structure
        if (!welcomeMessage) {
            welcomeMessage = document.createElement('div');
            welcomeMessage.className = 'message bot-message';
            welcomeMessage.setAttribute('role', 'article');
            
            const avatar = document.createElement('div');
            avatar.className = 'message-avatar';
            avatar.setAttribute('aria-hidden', 'true');
            avatar.innerHTML = '<img src="logo.png" alt="Chatbot" class="bot-avatar-img">';
            
            const content = document.createElement('div');
            content.className = 'message-content';
            
            const text = document.createElement('div');
            text.className = 'message-text';
            text.innerHTML = `
                <h3>Welcome to your Learning Assistant! 🎓</h3>
                <p>I'm here to help you with your studies and answer questions about your course materials. You can ask me about:</p>
                <ul>
                    <li>📚 Course content and concepts</li>
                    <li>📖 Study materials and resources</li>
                    <li>💡 Learning strategies and tips</li>
                    <li>❓ Assignment questions and clarifications</li>
                </ul>
                <p><strong>What would you like to learn about today?</strong></p>
            `;
            
            const time = document.createElement('div');
            time.className = 'message-time';
            time.setAttribute('aria-label', 'Message timestamp');
            const timeSpan = document.createElement('span');
            timeSpan.id = 'welcomeTime';
            timeSpan.textContent = this.formatTime(new Date());
            time.appendChild(timeSpan);
            
            content.appendChild(text);
            content.appendChild(time);
            
            welcomeMessage.appendChild(avatar);
            welcomeMessage.appendChild(content);
        }
        
        this.chatContainer.appendChild(welcomeMessage);
        
        // Generate new conversation ID
        this.conversationId = this.generateConversationId();
        
        // Clear input field
        this.messageInput.value = '';
        this.updateCharCount();
        this.autoResizeTextarea();
        
        // Refresh chat history if sidebar is open
        if (this.historySidebar && !this.historySidebar.classList.contains('hidden')) {
            this.refreshChatHistory();
        }
        
        // Ultra-optimized scroll to top
        requestAnimationFrame(() => {
            this.chatContainer.scrollTop = 0;
        });
        
        // Focus on input for better UX
        this.messageInput.focus();
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

    // Chat History Management

    // Toggle history sidebar visibility
    toggleHistorySidebar() {
        if (!this.historySidebar) return;
        
        const isHidden = this.historySidebar.classList.contains('hidden');
        if (isHidden) {
            this.historySidebar.classList.remove('hidden');
            this.loadChatHistory();
        } else {
            this.historySidebar.classList.add('hidden');
        }
    }

    // Load chat history from backend or localStorage
    async loadChatHistory() {
        if (!this.historyList || !this.historyLoading || !this.historyEmpty) return;

        // Show loading state
        this.historyLoading.style.display = 'flex';
        this.historyEmpty.style.display = 'none';
        this.historyList.innerHTML = '';

        try {
            // Try to fetch from backend first
            const backendHistory = await this.fetchChatHistoryFromBackend();
            
            if (backendHistory && backendHistory.length > 0) {
                this.displayHistoryItems(backendHistory);
            } else {
                // Fallback to localStorage
                const localHistory = this.getChatHistoryFromLocal();
                if (localHistory && localHistory.length > 0) {
                    this.displayHistoryItems(localHistory);
                } else {
                    this.showEmptyHistory();
                }
            }
        } catch (error) {
            console.error('Error loading chat history:', error);
            // Fallback to localStorage on error
            const localHistory = this.getChatHistoryFromLocal();
            if (localHistory && localHistory.length > 0) {
                this.displayHistoryItems(localHistory);
            } else {
                this.showEmptyHistory();
            }
        } finally {
            this.historyLoading.style.display = 'none';
        }
    }

    // Refresh chat history (used after sending a message)
    refreshChatHistory() {
        if (this.historySidebar && !this.historySidebar.classList.contains('hidden')) {
            this.loadChatHistory();
        }
    }

    // Fetch chat history from backend API
    async fetchChatHistoryFromBackend() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/chat/sessions/${this.userId}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                const data = await response.json();
                if (data.sessions && data.sessions.length > 0) {
                    // Fetch detailed history for each session
                    const historyPromises = data.sessions.slice(0, 20).map(session => 
                        this.fetchSessionHistory(session.session_id)
                    );
                    const histories = await Promise.all(historyPromises);
                    return histories.filter(h => h !== null);
                }
            }
            return [];
        } catch (error) {
            console.error('Error fetching chat history from backend:', error);
            return [];
        }
    }

    // Fetch detailed history for a specific session
    async fetchSessionHistory(sessionId) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/chat/history/${this.userId}?session_id=${sessionId}&limit=1`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                const data = await response.json();
                if (data.history && data.history.length > 0) {
                    const record = data.history[0];
                    return {
                        session_id: sessionId,
                        user_message: record.user_message || '',
                        bot_response: record.bot_response || '',
                        created_at: record.created_at || new Date().toISOString()
                    };
                }
            }
            return null;
        } catch (error) {
            console.error('Error fetching session history:', error);
            return null;
        }
    }

    // Get chat history from localStorage (fallback)
    getChatHistoryFromLocal() {
        try {
            const historyKey = `chat_history_${this.userId}`;
            const historyJson = localStorage.getItem(historyKey);
            if (historyJson) {
                const history = JSON.parse(historyJson);
                // Return most recent 20 items
                return history.slice(-20).reverse();
            }
        } catch (error) {
            console.error('Error reading chat history from localStorage:', error);
        }
        return [];
    }

    // Save conversation to localStorage
    saveConversationToLocal(userMessage, botResponse) {
        try {
            const historyKey = `chat_history_${this.userId}`;
            let history = this.getChatHistoryFromLocal();
            
            history.push({
                session_id: this.conversationId,
                user_message: userMessage,
                bot_response: botResponse,
                created_at: new Date().toISOString()
            });

            // Keep only last 50 conversations
            if (history.length > 50) {
                history = history.slice(-50);
            }

            localStorage.setItem(historyKey, JSON.stringify(history));
        } catch (error) {
            console.error('Error saving conversation to localStorage:', error);
        }
    }

    // Display history items in the sidebar
    displayHistoryItems(items) {
        if (!this.historyList) return;

        this.historyList.innerHTML = '';
        this.historyEmpty.style.display = 'none';

        items.forEach(item => {
            const historyItem = this.createHistoryItem(item);
            this.historyList.appendChild(historyItem);
        });
    }

    // Create a history item element
    createHistoryItem(item) {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'history-item';
        itemDiv.dataset.sessionId = item.session_id;

        // Format time
        const date = new Date(item.created_at);
        const timeStr = this.formatTime(date);
        const dateStr = date.toLocaleDateString([], { month: 'short', day: 'numeric' });

        // Get preview text
        const userMsg = item.user_message || 'No message';
        const botMsg = item.bot_response || 'No response';
        const botPreview = botMsg.length > 100 ? botMsg.substring(0, 100) + '...' : botMsg;

        itemDiv.innerHTML = `
            <div class="history-item-header">
                <span class="history-item-time">${timeStr} • ${dateStr}</span>
                <button class="history-item-delete" aria-label="Delete chat" data-session-id="${item.session_id}">
                    <i class="fas fa-times" aria-hidden="true"></i>
                    <span class="delete-tooltip">Delete</span>
                </button>
            </div>
            <div class="history-item-user">${this.escapeHtml(userMsg)}</div>
            <div class="history-item-bot">${this.escapeHtml(botPreview)}</div>
        `;

        // Add click handler to load conversation (excluding delete button clicks)
        itemDiv.addEventListener('click', (e) => {
            // Don't trigger load if clicking the delete button
            if (!e.target.closest('.history-item-delete')) {
                this.loadConversationFromHistory(item.session_id);
            }
        });

        // Add delete button click handler
        const deleteBtn = itemDiv.querySelector('.history-item-delete');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent triggering the item click
                this.deleteHistoryItem(item.session_id, itemDiv);
            });
        }

        return itemDiv;
    }

    // Show empty history state
    showEmptyHistory() {
        if (!this.historyList || !this.historyEmpty) return;
        
        this.historyList.innerHTML = '';
        this.historyEmpty.style.display = 'flex';
    }

    // Load a conversation from history
    async loadConversationFromHistory(sessionId) {
        try {
            // Update active state in history list
            const historyItems = this.historyList.querySelectorAll('.history-item');
            historyItems.forEach(item => {
                if (item.dataset.sessionId === sessionId) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });

            // Fetch full conversation history
            const response = await fetch(`${this.apiBaseUrl}/chat/history/${this.userId}?session_id=${sessionId}&limit=100`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                const data = await response.json();
                if (data.history && data.history.length > 0) {
                    // Update conversation ID
                    this.conversationId = sessionId;

                    // Clear current chat (keep welcome message)
                    const welcomeMessage = this.chatContainer.querySelector('.bot-message');
                    while (this.chatContainer.firstChild) {
                        this.chatContainer.removeChild(this.chatContainer.firstChild);
                    }
                    if (welcomeMessage) {
                        this.chatContainer.appendChild(welcomeMessage);
                    }

                    // Load messages from history
                    data.history.forEach(record => {
                        if (record.user_message) {
                            this.addMessageToChat(record.user_message, 'user');
                        }
                        if (record.bot_response) {
                            this.addMessageToChat(record.bot_response, 'bot');
                        }
                    });

                    // Scroll to bottom
                    this.scrollToBottom();
                }
            } else {
                // Fallback: try loading from localStorage
                this.loadConversationFromLocal(sessionId);
            }
        } catch (error) {
            console.error('Error loading conversation from history:', error);
            // Fallback: try loading from localStorage
            this.loadConversationFromLocal(sessionId);
        }
    }

    // Delete a chat history item
    async deleteHistoryItem(sessionId, itemElement) {
        // Confirm deletion
        if (!confirm('Are you sure you want to delete this chat?')) {
            return;
        }

        try {
            // Try to delete from backend first
            const response = await fetch(`${this.apiBaseUrl}/chat/session/${this.userId}/${sessionId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok || response.status === 404) {
                // 404 means it was already deleted or doesn't exist - still successful
                console.log(`Chat session ${sessionId} deleted from backend`);
            } else {
                console.warn(`Failed to delete session from backend: ${response.status}`);
            }
        } catch (error) {
            console.error('Error deleting chat session from backend:', error);
            // Continue with localStorage deletion even if backend fails
        }

        // Delete from localStorage
        try {
            const historyKey = `chat_history_${this.userId}`;
            const historyJson = localStorage.getItem(historyKey);
            if (historyJson) {
                let history = JSON.parse(historyJson);
                history = history.filter(item => item.session_id !== sessionId);
                localStorage.setItem(historyKey, JSON.stringify(history));
            }
        } catch (error) {
            console.error('Error deleting chat session from localStorage:', error);
        }

        // Remove from UI immediately
        if (itemElement && itemElement.parentNode) {
            itemElement.remove();
        }

        // If this was the active conversation, start a new chat
        if (this.conversationId === sessionId) {
            this.newChat();
        }

        // Refresh history list if empty
        const remainingItems = this.historyList.querySelectorAll('.history-item');
        if (remainingItems.length === 0) {
            this.showEmptyHistory();
        }
    }

    // Load conversation from localStorage (fallback)
    loadConversationFromLocal(sessionId) {
        try {
            const history = this.getChatHistoryFromLocal();
            const sessionHistory = history.filter(item => item.session_id === sessionId);

            if (sessionHistory.length > 0) {
                // Update conversation ID
                this.conversationId = sessionId;

                // Clear current chat (keep welcome message)
                const welcomeMessage = this.chatContainer.querySelector('.bot-message');
                while (this.chatContainer.firstChild) {
                    this.chatContainer.removeChild(this.chatContainer.firstChild);
                }
                if (welcomeMessage) {
                    this.chatContainer.appendChild(welcomeMessage);
                }

                // Load messages from history
                sessionHistory.forEach(item => {
                    if (item.user_message) {
                        this.addMessageToChat(item.user_message, 'user');
                    }
                    if (item.bot_response) {
                        this.addMessageToChat(item.bot_response, 'bot');
                    }
                });

                // Scroll to bottom
                this.scrollToBottom();
            }
        } catch (error) {
            console.error('Error loading conversation from localStorage:', error);
            this.showError('Failed to load conversation from history.');
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
    
    // Initialize chat history sidebar (hidden by default on mobile, visible on desktop)
    if (window.innerWidth <= 1024) {
        if (chatbot.historySidebar) {
            chatbot.historySidebar.classList.add('hidden');
        }
    } else {
        // Load history on desktop by default
        if (chatbot.historySidebar) {
            chatbot.loadChatHistory();
        }
    }
    
    // Handle window resize to show/hide sidebar appropriately
    window.addEventListener('resize', () => {
        if (window.innerWidth <= 1024 && chatbot.historySidebar) {
            if (!chatbot.historySidebar.classList.contains('hidden')) {
                chatbot.historySidebar.classList.add('hidden');
            }
        }
    });
    
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
