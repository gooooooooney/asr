export class IntentDetector {
    constructor() {
        this.listeners = {};
        this.geminiApiKey = null;
        this.intentPatterns = {
            search: {
                keywords: ['查找', '搜索', '查询', '了解', '知道', '是什么', '怎么样'],
                contextPatterns: [
                    { pattern: /忘记.*哪里.*买/, intent: '查找购买记录' },
                    { pattern: /发生.*危险|事故|意外/, intent: '搜索事故新闻' },
                    { pattern: /.*公司.*出售|销售|生产/, intent: '搜索公司信息' },
                    { pattern: /了解.*最新|新闻|消息/, intent: '搜索最新资讯' }
                ]
            },
            memory: {
                keywords: ['记得', '忘记', '昨天', '前天', '上次'],
                contextPatterns: [
                    { pattern: /忘记.*昨天|今天|前天/, intent: '查找历史记录' },
                    { pattern: /记得.*什么时候/, intent: '查找时间记录' }
                ]
            }
        };
    }

    setGeminiApiKey(apiKey) {
        this.geminiApiKey = apiKey;
    }

    async detectIntent(text) {
        // 首先尝试规则匹配
        const ruleBasedIntent = this.detectByRules(text);
        
        if (ruleBasedIntent) {
            this.emit('intent', ruleBasedIntent);
            return ruleBasedIntent;
        }

        // 如果没有匹配规则，使用语义理解
        if (this.hasQuestionIndicators(text)) {
            const semanticIntent = await this.detectBySemantic(text);
            if (semanticIntent) {
                this.emit('intent', semanticIntent);
                return semanticIntent;
            }
        }

        return null;
    }

    detectByRules(text) {
        const cleanText = text.replace(/[。，！？,.!?]/g, ' ').trim();
        
        for (const [type, config] of Object.entries(this.intentPatterns)) {
            // 检查上下文模式
            for (const contextPattern of config.contextPatterns) {
                if (contextPattern.pattern.test(cleanText)) {
                    return {
                        type: type,
                        subType: contextPattern.intent,
                        query: this.extractQuery(cleanText, type),
                        confidence: 0.9,
                        originalText: text
                    };
                }
            }
            
            // 检查关键词
            const hasKeyword = config.keywords.some(keyword => cleanText.includes(keyword));
            if (hasKeyword) {
                const query = this.extractQuery(cleanText, type);
                if (query) {
                    return {
                        type: type,
                        subType: 'general',
                        query: query,
                        confidence: 0.7,
                        originalText: text
                    };
                }
            }
        }
        
        return null;
    }

    hasQuestionIndicators(text) {
        const indicators = [
            '吗', '呢', '么', '？', '?',
            '什么', '怎么', '为什么', '哪里', '哪个', '谁', '多少',
            '是不是', '有没有', '能不能'
        ];
        
        return indicators.some(indicator => text.includes(indicator));
    }

    async detectBySemantic(text) {
        if (!this.geminiApiKey) {
            // 没有API key时的降级处理
            return this.fallbackSemanticDetection(text);
        }

        // TODO: 调用Gemini API进行语义理解
        return this.fallbackSemanticDetection(text);
    }

    fallbackSemanticDetection(text) {
        // 简单的语义规则
        const patterns = [
            { regex: /.*买.*东西|商品|产品/, type: 'search', subType: '购物查询' },
            { regex: /.*发生.*什么|事情|事故/, type: 'search', subType: '事件查询' },
            { regex: /.*怎么.*做|办|处理/, type: 'search', subType: '方法查询' },
            { regex: /.*是什么|什么是/, type: 'search', subType: '定义查询' }
        ];

        for (const pattern of patterns) {
            if (pattern.regex.test(text)) {
                return {
                    type: pattern.type,
                    subType: pattern.subType,
                    query: this.extractQuery(text, pattern.type),
                    confidence: 0.6,
                    originalText: text
                };
            }
        }

        return null;
    }

    extractQuery(text, type) {
        // 移除问句标记
        let query = text.replace(/[？?。！!，,]/g, '').trim();
        
        // 移除常见的前缀
        const prefixes = [
            '我想', '我要', '请', '帮我', '帮忙', '能不能', '可以',
            '我忘记', '忘记了', '记不清', '不知道'
        ];
        
        for (const prefix of prefixes) {
            if (query.startsWith(prefix)) {
                query = query.substring(prefix.length).trim();
            }
        }
        
        // 提取核心查询内容
        const extractPatterns = [
            /(?:查找|搜索|了解|知道)(.+)/,
            /(.+?)(?:是什么|怎么样|在哪里)/,
            /关于(.+)的/,
            /(.+)(?:的信息|的资料|的情况)/
        ];
        
        for (const pattern of extractPatterns) {
            const match = query.match(pattern);
            if (match && match[1]) {
                return match[1].trim();
            }
        }
        
        // 如果没有匹配到特定模式，返回处理后的文本
        return query.length > 2 ? query : null;
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