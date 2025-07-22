export class SearchManager {
    constructor() {
        this.geminiApiKey = null;
        this.ragKnowledgeBase = [];
    }

    setGeminiApiKey(apiKey) {
        this.geminiApiKey = apiKey;
    }

    // RAG知识库搜索
    async searchRAG(query) {
        try {
            // 简单的相似度匹配
            const results = this.ragKnowledgeBase
                .filter(item => {
                    const content = (item.title + ' ' + item.content).toLowerCase();
                    const queryLower = query.toLowerCase();
                    const keywords = queryLower.split(' ');
                    
                    // 计算匹配的关键词数量
                    let matchCount = 0;
                    for (const keyword of keywords) {
                        if (content.includes(keyword)) {
                            matchCount++;
                        }
                    }
                    
                    return matchCount > 0;
                })
                .map(item => ({
                    ...item,
                    source: 'RAG'
                }))
                .slice(0, 3);
                
            return results;
        } catch (error) {
            console.error('RAG搜索失败:', error);
            return [];
        }
    }

    // 外部搜索（使用Gemini或其他API）
    async searchExternal(query) {
        try {
            if (this.geminiApiKey) {
                return await this.searchWithGemini(query);
            } else {
                return await this.searchWithMockData(query);
            }
        } catch (error) {
            console.error('外部搜索失败:', error);
            return [];
        }
    }

    async searchWithGemini(query) {
        if (!this.geminiApiKey) {
            return this.searchWithMockData(query);
        }

        try {
            const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=${this.geminiApiKey}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    contents: [{
                        parts: [{
                            text: `请搜索关于"${query}"的最新信息，并返回3个相关结果。

请以JSON格式返回，格式如下：
[
  {
    "title": "结果标题",
    "snippet": "结果摘要（50字以内）",
    "relevance": 0.0-1.0
  }
]

只返回JSON数组，不要有其他内容。`
                        }]
                    }],
                    generationConfig: {
                        temperature: 0.7,
                        maxOutputTokens: 500,
                        responseMimeType: "application/json"
                    }
                })
            });

            if (!response.ok) {
                throw new Error('Gemini search failed');
            }

            const data = await response.json();
            const responseText = data.candidates?.[0]?.content?.parts?.[0]?.text;
            
            if (responseText) {
                try {
                    const results = JSON.parse(responseText);
                    return results.map(r => ({
                        ...r,
                        source: 'Gemini',
                        timestamp: new Date().toISOString()
                    }));
                } catch (e) {
                    console.error('Failed to parse Gemini search results');
                }
            }
        } catch (error) {
            console.error('Gemini search error:', error);
        }

        return this.searchWithMockData(query);
    }

    async searchWithMockData(query) {
        const mockResults = [
            {
                title: `关于"${query}"的搜索结果`,
                snippet: `这是使用外部搜索引擎找到的关于${query}的最新信息...`,
                source: 'External',
                timestamp: new Date().toISOString()
            }
        ];
        
        await new Promise(resolve => setTimeout(resolve, 500));
        return mockResults;
    }

    // 旧的search方法保留兼容性
    async search(query) {
        const ragResults = await this.searchRAG(query);
        if (ragResults.length > 0) {
            return ragResults;
        }
        return await this.searchExternal(query);
    }

    // 添加知识到RAG库
    addToRAG(title, content, metadata = {}) {
        this.ragKnowledgeBase.push({
            id: Date.now().toString(),
            title,
            content,
            metadata,
            timestamp: new Date().toISOString()
        });
    }

    summarizeResults(results) {
        if (results.length === 0) {
            return '没有找到相关搜索结果';
        }

        const sources = [...new Set(results.map(r => r.source))];
        const sourceText = sources.includes('RAG') ? '知识库' : '网络';
        
        const firstResult = results[0];
        let summary = `从${sourceText}找到${results.length}个结果。`;
        
        // 提取关键信息，确保不超过40字
        const snippet = firstResult.snippet || firstResult.content || '';
        const shortSnippet = snippet.substring(0, 20);
        summary += shortSnippet;
        
        if (summary.length > 40) {
            return summary.substring(0, 37) + '...';
        }
        
        return summary;
    }
}