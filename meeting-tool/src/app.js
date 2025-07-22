import { SpeechRecognitionManager } from './speechRecognition.js';
import { TenVADManager } from './tenVad.js';
import { GeminiIntentDetector } from './geminiIntentDetector.js';
import { SearchManager } from './searchManager.js';
import { TTSManager } from './tts.js';
import { WakeWordDetector } from './wakeWord.js';

class MeetingAssistant {
    constructor() {
        this.speechRecognition = new SpeechRecognitionManager();
        this.vad = new TenVADManager();
        this.intentDetector = new GeminiIntentDetector();
        this.searchManager = new SearchManager();
        this.tts = new TTSManager();
        this.wakeWordDetector = new WakeWordDetector();
        
        this.isRecording = false;
        this.fullTranscript = '';
        this.lastProcessedLength = 0;
        this.lastSearchResults = null;
        this.isWakeWordActive = false;
        this.isInitialized = false;
        
        this.initializeUI();
        this.setupEventListeners();
        this.checkInitialization();
    }

    initializeUI() {
        this.startBtn = document.getElementById('startBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.settingsBtn = document.getElementById('settingsBtn');
        this.recordingStatus = document.getElementById('recordingStatus');
        this.vadStatus = document.getElementById('vadStatus');
        this.transcriptionBox = document.getElementById('transcription');
        this.functionCallsBox = document.getElementById('functionCalls');
        this.searchResultsBox = document.getElementById('searchResults');
        this.searchHistoryBox = document.getElementById('searchHistory');
        this.settingsPanel = document.getElementById('settingsPanel');
        this.geminiApiKeyInput = document.getElementById('geminiApiKey');
        this.saveSettingsBtn = document.getElementById('saveSettings');
        this.closeSettingsBtn = document.getElementById('closeSettings');
        
        // 加载保存的设置
        this.loadSettings();
    }

    setupEventListeners() {
        this.startBtn.addEventListener('click', () => this.startRecording());
        this.stopBtn.addEventListener('click', () => this.stopRecording());
        this.settingsBtn.addEventListener('click', () => this.showSettings());
        this.saveSettingsBtn.addEventListener('click', () => this.saveSettings());
        this.closeSettingsBtn.addEventListener('click', () => this.hideSettings());
        
        this.speechRecognition.on('transcript', (text) => this.handleTranscript(text));
        this.speechRecognition.on('error', (error) => this.handleError(error));
        
        this.vad.on('speechStart', () => this.handleSpeechStart());
        this.vad.on('speechEnd', () => this.handleSpeechEnd());
        
        this.intentDetector.on('intent', (intent) => this.handleIntent(intent));
        this.wakeWordDetector.on('wakeWordDetected', () => this.handleWakeWord());
    }

    async startRecording() {
        try {
            this.isRecording = true;
            this.startBtn.disabled = true;
            this.stopBtn.disabled = false;
            this.recordingStatus.textContent = '录音中...';
            this.recordingStatus.classList.add('recording-active');
            
            await this.speechRecognition.start();
            await this.vad.start();
            
        } catch (error) {
            console.error('启动录音失败:', error);
            this.handleError(error);
        }
    }

    stopRecording() {
        this.isRecording = false;
        this.startBtn.disabled = false;
        this.stopBtn.disabled = true;
        this.recordingStatus.textContent = '未开始';
        this.recordingStatus.classList.remove('recording-active');
        
        this.speechRecognition.stop();
        this.vad.stop();
    }

    handleTranscript(text) {
        this.fullTranscript = text;
        this.transcriptionBox.textContent = text;
        this.transcriptionBox.scrollTop = this.transcriptionBox.scrollHeight;
        
        const newText = text.substring(this.lastProcessedLength);
        if (newText.length >= 10) {
            this.checkForFunctionCall(text, 'char');
        }
    }

    handleSpeechStart() {
        this.vadStatus.textContent = 'VAD: 说话中';
        this.vadStatus.classList.add('active');
    }

    handleSpeechEnd() {
        this.vadStatus.textContent = 'VAD: 静音';
        this.vadStatus.classList.remove('active');
        
        if (this.fullTranscript.length > this.lastProcessedLength) {
            this.checkForFunctionCall(this.fullTranscript, 'silence');
        }
    }

    async checkForFunctionCall(text, triggerType = 'char') {
        // 检查唤醒词（使用最近的文本）
        const recentStart = Math.max(0, text.length - 50);
        const recentText = text.substring(recentStart);
        this.wakeWordDetector.detect(recentText);
        
        // 检查意图（使用完整文本）
        await this.intentDetector.detectIntent(text, triggerType);
    }

    async handleIntent(intent) {
        const timestamp = new Date().toLocaleTimeString();
        const callElement = document.createElement('div');
        callElement.className = 'function-call-item';
        
        // 显示触发类型和是否重复
        let statusText = `<strong>${intent.type}</strong>`;
        if (intent.isDuplicate) {
            statusText += ` <span style="color: #f39c12;">[重复]</span>`;
        }
        if (intent.triggerType) {
            statusText += ` <small>(${intent.triggerType === 'char' ? '字数触发' : '静默触发'})</small>`;
        }
        
        callElement.innerHTML = `
            <span class="timestamp">${timestamp}</span>
            ${statusText}: ${intent.query}
            <span class="confidence">置信度: ${(intent.confidence * 100).toFixed(0)}%</span>
        `;
        
        if (intent.isDuplicate && intent.duplicateReason) {
            callElement.innerHTML += `<br><small style="color: #7f8c8d;">${intent.duplicateReason}</small>`;
        }
        
        this.functionCallsBox.appendChild(callElement);
        this.functionCallsBox.scrollTop = this.functionCallsBox.scrollHeight;
        
        // 更新搜索历史显示
        this.updateSearchHistoryDisplay();
        
        if (intent.type === 'search' || intent.type === 'memory') {
            // 首先尝试RAG搜索
            const ragResults = await this.searchManager.searchRAG(intent.query);
            
            // 如果RAG没有结果，使用外部搜索
            let results = ragResults;
            if (!ragResults || ragResults.length === 0) {
                results = await this.searchManager.searchExternal(intent.query);
            }
            
            this.displaySearchResults(results);
            this.lastSearchResults = results;
            
            // 不自动播放TTS，等待唤醒词
        }
    }
    
    async handleWakeWord() {
        this.isWakeWordActive = true;
        
        // 显示唤醒状态
        const wakeIndicator = document.createElement('div');
        wakeIndicator.className = 'wake-indicator';
        wakeIndicator.textContent = '小爱同学已唤醒';
        document.body.appendChild(wakeIndicator);
        
        setTimeout(() => {
            wakeIndicator.remove();
        }, 2000);
        
        // 如果有最近的搜索结果，播放总结
        if (this.lastSearchResults && this.lastSearchResults.length > 0) {
            const summary = this.searchManager.summarizeResults(this.lastSearchResults);
            await this.tts.speak(summary);
        } else {
            await this.tts.speak('我在听，请问有什么可以帮助您？');
        }
        
        // 5秒后关闭唤醒状态
        setTimeout(() => {
            this.isWakeWordActive = false;
        }, 5000);
    }

    displaySearchResults(results) {
        this.searchResultsBox.innerHTML = '';
        results.forEach(result => {
            const resultElement = document.createElement('div');
            resultElement.className = 'search-result-item';
            if (result.source === 'RAG') {
                resultElement.classList.add('rag-result');
            }
            
            const sourceTag = result.source === 'RAG' ? 
                '<span class="source-tag rag">知识库</span>' : 
                '<span class="source-tag external">外部搜索</span>';
            
            resultElement.innerHTML = `
                <h3>${result.title}${sourceTag}</h3>
                <p>${result.snippet || result.content || ''}</p>
            `;
            this.searchResultsBox.appendChild(resultElement);
        });
    }

    handleError(error) {
        console.error('错误:', error);
        alert('发生错误: ' + error.message);
    }
    
    showSettings() {
        this.settingsPanel.style.display = 'block';
    }
    
    hideSettings() {
        this.settingsPanel.style.display = 'none';
    }
    
    saveSettings() {
        const apiKey = this.geminiApiKeyInput.value.trim();
        if (apiKey) {
            localStorage.setItem('geminiApiKey', apiKey);
            this.intentDetector.setGeminiApiKey(apiKey);
            this.searchManager.setGeminiApiKey(apiKey);
            alert('设置已保存');
        }
        this.hideSettings();
    }
    
    loadSettings() {
        const apiKey = localStorage.getItem('geminiApiKey');
        if (apiKey) {
            this.geminiApiKeyInput.value = apiKey;
            this.intentDetector.setGeminiApiKey(apiKey);
            this.searchManager.setGeminiApiKey(apiKey);
        }
    }
    
    async checkInitialization() {
        const apiKey = localStorage.getItem('geminiApiKey');
        
        if (!apiKey) {
            // Show settings panel if no API key
            this.showSettings();
            this.showMessage('请先设置 Gemini API 密钥', 'warning');
            this.startBtn.disabled = true;
        } else {
            // Test API connection
            await this.testApiConnection();
        }
    }
    
    async testApiConnection() {
        try {
            this.showMessage('正在测试 API 连接...', 'info');
            await this.intentDetector.testConnection();
            this.showMessage('API 连接成功！', 'success');
            this.isInitialized = true;
            this.startBtn.disabled = false;
        } catch (error) {
            this.showMessage(`API 连接失败: ${error.message}`, 'error');
            this.startBtn.disabled = true;
            this.showSettings();
        }
    }
    
    showMessage(message, type = 'info') {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message message-${type}`;
        messageDiv.textContent = message;
        messageDiv.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            padding: 15px 25px;
            border-radius: 5px;
            z-index: 1002;
            animation: slideDown 0.3s ease-out;
        `;
        
        // Set color based on type
        const colors = {
            info: '#3498db',
            success: '#2ecc71',
            warning: '#f39c12',
            error: '#e74c3c'
        };
        messageDiv.style.backgroundColor = colors[type] || colors.info;
        messageDiv.style.color = 'white';
        
        document.body.appendChild(messageDiv);
        
        setTimeout(() => {
            messageDiv.remove();
        }, 3000);
    }
    
    async saveSettings() {
        const apiKey = this.geminiApiKeyInput.value.trim();
        if (apiKey) {
            localStorage.setItem('geminiApiKey', apiKey);
            this.intentDetector.setGeminiApiKey(apiKey);
            this.searchManager.setGeminiApiKey(apiKey);
            
            // Test connection after saving
            await this.testApiConnection();
            
            if (this.isInitialized) {
                this.hideSettings();
            }
        } else {
            this.showMessage('请输入有效的 API 密钥', 'warning');
        }
    }
    
    updateSearchHistoryDisplay() {
        const history = this.intentDetector.getSearchHistory();
        
        if (history.length === 0) {
            this.searchHistoryBox.innerHTML = '<div class="history-placeholder">暂无搜索历史</div>';
        } else {
            this.searchHistoryBox.innerHTML = history.map((item, index) => `
                <div class="history-item">
                    <span style="color: #3498db;">${index + 1}.</span> 
                    [${item.type}] ${item.query}
                    <small style="float: right; color: #7f8c8d;">${new Date(item.timestamp).toLocaleTimeString()}</small>
                </div>
            `).join('');
        }
    }
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
@keyframes slideDown {
    from {
        transform: translate(-50%, -100%);
        opacity: 0;
    }
    to {
        transform: translate(-50%, 0);
        opacity: 1;
    }
}
`;
document.head.appendChild(style);

window.addEventListener('DOMContentLoaded', () => {
    new MeetingAssistant();
});