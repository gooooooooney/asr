export class GeminiIntentDetector {
    constructor() {
        this.listeners = {};
        this.geminiApiKey = null;
        this.apiEndpoint = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent';
        
        // Context management
        this.contextWindow = 200; // Keep last 200 characters as context
        this.newTextThreshold = 10; // Process every 10 new characters
        this.recentContext = '';
        this.lastProcessedIndex = 0;
        this.lastProcessedText = ''; // 避免重复处理相同文本
        
        // Rate limiting
        this.lastApiCall = 0;
        this.minApiInterval = 1000; // Minimum 1 second between API calls
        
        // Intent queue
        this.pendingCheck = null;
        
        // Trigger management
        this.lastTriggerType = null; // 'char' or 'silence'
        this.lastTriggerTime = 0;
        this.SILENCE_DURATION = 1500;
        
        // Search history for deduplication
        this.searchHistory = [];
        this.MAX_HISTORY_SIZE = 5;
    }

    setGeminiApiKey(apiKey) {
        this.geminiApiKey = apiKey;
    }

    async testConnection() {
        if (!this.geminiApiKey) {
            throw new Error('Gemini API key not set');
        }

        try {
            const response = await fetch(`${this.apiEndpoint}?key=${this.geminiApiKey}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    contents: [{
                        parts: [{
                            text: "Hello, this is a test. Please respond with 'Connection successful'."
                        }]
                    }],
                    generationConfig: {
                        temperature: 0.1,
                        maxOutputTokens: 50
                    }
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(`API Error: ${error.error?.message || response.statusText}`);
            }

            const data = await response.json();
            console.log('Gemini API test response:', data);
            return true;
        } catch (error) {
            console.error('Gemini API test failed:', error);
            throw error;
        }
    }

    async detectIntent(fullText, triggerType = 'char') {
        console.log(`[GeminiIntentDetector] detectIntent called - trigger: ${triggerType}, text length: ${fullText.length}`);
        
        if (!this.geminiApiKey) {
            console.warn('[GeminiIntentDetector] Gemini API key not set, skipping intent detection');
            return null;
        }

        // Update context
        this.recentContext = fullText;
        
        // Check if we have enough new text
        const newText = fullText.substring(this.lastProcessedIndex);
        console.log(`[GeminiIntentDetector] New text: "${newText}", length: ${newText.length}, threshold: ${this.newTextThreshold}`);
        
        if (triggerType === 'char' && newText.length < this.newTextThreshold) {
            console.log('[GeminiIntentDetector] Not enough new text for char trigger');
            return null;
        }

        // Avoid double trigger (char then silence)
        const now = Date.now();
        if (triggerType === 'silence' && this.lastTriggerType === 'char') {
            const timeSinceLastTrigger = now - this.lastTriggerTime;
            if (timeSinceLastTrigger < this.SILENCE_DURATION * 2) {
                console.log(`[GeminiIntentDetector] Skipping silence trigger after recent char trigger (${timeSinceLastTrigger}ms < ${this.SILENCE_DURATION * 2}ms)`);
                return null;
            }
        }

        // Extract relevant context
        const contextStart = Math.max(0, fullText.length - this.contextWindow);
        const context = fullText.substring(contextStart);
        console.log(`[GeminiIntentDetector] Context for API: "${context}"`);
        
        // Check if same as last processed
        if (context === this.lastProcessedText && triggerType === 'silence') {
            console.log('[GeminiIntentDetector] Skipping: no new content since last check');
            return null;
        }

        // Rate limiting
        const timeSinceLastCall = now - this.lastApiCall;
        if (timeSinceLastCall < this.minApiInterval) {
            console.log(`[GeminiIntentDetector] Rate limited: ${timeSinceLastCall}ms < ${this.minApiInterval}ms`);
            // Queue the check
            if (this.pendingCheck) {
                clearTimeout(this.pendingCheck);
            }
            this.pendingCheck = setTimeout(() => {
                this.detectIntent(fullText, triggerType);
            }, this.minApiInterval - timeSinceLastCall);
            return null;
        }

        // Update state
        this.lastProcessedIndex = fullText.length;
        this.lastProcessedText = context;
        this.lastApiCall = now;
        this.lastTriggerType = triggerType;
        this.lastTriggerTime = now;

        try {
            console.log('[GeminiIntentDetector] Calling Gemini API...');
            const intent = await this.callGeminiAPI(context);
            console.log('[GeminiIntentDetector] API response:', intent);
            
            if (intent) {
                // Add to history if not duplicate
                if (intent.hasIntent && !intent.isDuplicate && intent.type !== 'none') {
                    this.addToHistory({
                        type: intent.type,
                        query: intent.query,
                        timestamp: new Date().toISOString()
                    });
                }
                
                // Emit intent with trigger info
                this.emit('intent', {
                    ...intent,
                    triggerType,
                    context: context
                });
                return intent;
            }
        } catch (error) {
            console.error('Intent detection error:', error);
        }

        return null;
    }

    isEndOfSentence(text) {
        return /[。！？.!?]$/.test(text.trim());
    }

    async callGeminiAPI(text) {
        const searchHistoryText = this.formatSearchHistory();
        
        const prompt = `你是一个智能助手的意图识别系统。请分析用户说的话，判断用户是否有需要执行的任务。

用户说: "${text}"

之前已经执行的搜索历史：
${searchHistoryText}

请以JSON格式回复，格式如下：
{
  "hasIntent": true/false,
  "type": "search" | "memory" | "reminder" | "none",
  "query": "提取的关键查询内容",
  "confidence": 0.0-1.0,
  "isDuplicate": true/false,
  "duplicateReason": "如果是重复，说明原因"
}

判断规则：
1. 如果用户在询问信息、查找内容、了解情况，type为"search"
2. 如果用户在回忆、查找历史记录，type为"memory"
3. 如果用户要求提醒或记录，type为"reminder"
4. 如果没有明确意图，hasIntent为false，type为"none"
5. 如果查询内容与历史记录相似或相同，isDuplicate为true

只返回JSON，不要有其他内容。`;

        console.log('[GeminiIntentDetector] Sending prompt to Gemini:');
        console.log('================== PROMPT START ==================');
        console.log(prompt);
        console.log('================== PROMPT END ====================');
        
        try {
            const response = await fetch(`${this.apiEndpoint}?key=${this.geminiApiKey}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    contents: [{
                        parts: [{
                            text: prompt
                        }]
                    }],
                    generationConfig: {
                        temperature: 0.3,
                        maxOutputTokens: 200,
                        responseMimeType: "application/json"
                    }
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(`API Error: ${error.error?.message || response.statusText}`);
            }

            const data = await response.json();
            console.log('[GeminiIntentDetector] Raw API response:', JSON.stringify(data, null, 2));
            
            const responseText = data.candidates?.[0]?.content?.parts?.[0]?.text;
            
            if (!responseText) {
                console.log('[GeminiIntentDetector] No response text from API');
                return null;
            }
            
            console.log('[GeminiIntentDetector] Response text:', responseText);

            try {
                const results = JSON.parse(responseText);
                console.log('[GeminiIntentDetector] Parsed result:', results);
                
                // Handle array of results
                const intents = Array.isArray(results) ? results : [results];
                
                // Find the first valid intent (not 'none' type)
                const validIntent = intents.find(intent => 
                    intent.hasIntent && intent.type !== 'none'
                );
                
                if (validIntent) {
                    console.log('[GeminiIntentDetector] Intent detected!', validIntent);
                    return {
                        hasIntent: validIntent.hasIntent,
                        type: validIntent.type,
                        subType: this.getSubType(validIntent.type, text),
                        query: validIntent.query || this.extractQuery(text),
                        confidence: validIntent.confidence || 0.8,
                        isDuplicate: validIntent.isDuplicate || false,
                        duplicateReason: validIntent.duplicateReason || '',
                        originalText: text
                    };
                } else {
                    console.log('[GeminiIntentDetector] No valid intent detected (all are none or no intent)');
                    return null;
                }
            } catch (parseError) {
                console.error('Failed to parse Gemini response:', responseText);
            }
        } catch (error) {
            console.error('Gemini API call failed:', error);
        }

        return null;
    }

    getSubType(type, text) {
        // Provide more specific subtypes based on content
        if (type === 'search') {
            if (text.includes('公司') || text.includes('产品')) {
                return '商业查询';
            } else if (text.includes('新闻') || text.includes('事故')) {
                return '新闻查询';
            } else if (text.includes('怎么') || text.includes('如何')) {
                return '方法查询';
            }
            return '一般查询';
        } else if (type === 'memory') {
            if (text.includes('昨天') || text.includes('今天')) {
                return '时间查询';
            } else if (text.includes('买') || text.includes('购')) {
                return '购物记录';
            }
            return '历史查询';
        }
        return 'general';
    }

    extractQuery(text) {
        // Simple query extraction as fallback
        const cleanText = text.replace(/[。，！？,.!?]/g, ' ').trim();
        
        // Remove common prefixes
        const prefixes = ['我想', '我要', '请', '帮我', '能不能', '可以'];
        let query = cleanText;
        
        for (const prefix of prefixes) {
            if (query.startsWith(prefix)) {
                query = query.substring(prefix.length).trim();
                break;
            }
        }
        
        return query.length > 2 ? query : text;
    }

    addToHistory(item) {
        this.searchHistory.unshift(item);
        if (this.searchHistory.length > this.MAX_HISTORY_SIZE) {
            this.searchHistory.pop();
        }
    }

    formatSearchHistory() {
        if (this.searchHistory.length === 0) {
            return "无";
        }
        return this.searchHistory.map((item, index) => 
            `${index + 1}. [${item.type}] "${item.query}" (${new Date(item.timestamp).toLocaleTimeString()})`
        ).join('\n');
    }

    getSearchHistory() {
        return this.searchHistory;
    }

    clearHistory() {
        this.searchHistory = [];
    }

    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
    }

    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(callback => callback(data));
        }
    }
}