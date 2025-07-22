export class FunctionCallDetector {
    constructor() {
        this.listeners = {};
        this.patterns = {
            search: [
                /(?:siri|小助手|助手).*(?:帮我|帮忙|请).*(?:查找|查询|搜索|查一下|找一下|搜一下)/i,
                /(?:查找|查询|搜索|查一下|找一下|搜一下).*(?:关于|有关)/i,
                /(?:有什么|有哪些|什么).*(?:公司|产品|服务)/i,
                /(?:帮我|请).*(?:了解|查看|看看)/i
            ]
        };
    }

    detect(text) {
        const cleanText = text.replace(/[。，！？,.!?]/g, ' ').trim();
        
        for (const [type, patterns] of Object.entries(this.patterns)) {
            for (const pattern of patterns) {
                if (pattern.test(cleanText)) {
                    const query = this.extractQuery(cleanText, pattern);
                    if (query) {
                        this.emit('functionCall', {
                            type: type,
                            query: query,
                            originalText: text
                        });
                        return;
                    }
                }
            }
        }
    }

    extractQuery(text, pattern) {
        const keywordPatterns = [
            /(?:查找|查询|搜索|查一下|找一下|搜一下|了解|查看|看看)(.+)/i,
            /(.+?)(?:的信息|的资料|的情况|的公司|的产品)/i,
            /(?:关于|有关)(.+)/i,
            /什么(.+)/i
        ];

        for (const keywordPattern of keywordPatterns) {
            const match = text.match(keywordPattern);
            if (match && match[1]) {
                const query = match[1].trim();
                if (query.length > 2 && query.length < 50) {
                    return query;
                }
            }
        }

        const afterTrigger = text.split(/siri|小助手|助手|帮我|帮忙|请/i).pop();
        if (afterTrigger && afterTrigger.length > 2) {
            return afterTrigger.trim();
        }

        return null;
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