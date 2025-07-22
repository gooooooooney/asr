export class AIAppStore {
    constructor() {
        this.apps = [
            {
                id: 'link-summarizer',
                name: '链接总结器',
                description: '读取网页链接并智能总结内容',
                icon: '🔗',
                color: '#4CAF50'
            },
            {
                id: 'todo-generator',
                name: '待办生成器',
                description: '从笔记中提取待办事项并创建新笔记',
                icon: '✅',
                color: '#2196F3'
            },
            {
                id: 'note-merger',
                name: '笔记合并器',
                description: '智能合并多条笔记，去除口语化内容并整理结构',
                icon: '📝',
                color: '#FF9800'
            }
        ];
        
        this.geminiApiKey = null;
        this.jinaApiKey = null;
    }

    setApiKeys(geminiKey, jinaKey) {
        this.geminiApiKey = geminiKey;
        this.jinaApiKey = jinaKey;
    }

    getApps() {
        return this.apps;
    }

    async executeApp(appId, params) {
        switch (appId) {
            case 'link-summarizer':
                return await this.summarizeLink(params.url);
            case 'todo-generator':
                return await this.generateTodos(params.noteText, params.noteId);
            case 'note-merger':
                return await this.mergeNotes(params.notes);
            default:
                throw new Error(`Unknown app: ${appId}`);
        }
    }

    // 链接总结功能
    async summarizeLink(url) {
        try {
            // 首选使用 Jina API
            if (this.jinaApiKey) {
                return await this.summarizeWithJina(url);
            }
            
            // 备选使用免费的 Jina Reader API (无需 key)
            return await this.summarizeWithFreeJina(url);
        } catch (error) {
            console.error('Link summarization failed:', error);
            throw new Error('链接总结失败: ' + error.message);
        }
    }

    async summarizeWithFreeJina(url) {
        try {
            // 使用 Jina Reader API (免费版本)
            const response = await fetch(`https://r.jina.ai/${url}`, {
                headers: {
                    'Accept': 'application/json',
                    'X-With-Generated-Alt': 'true' // 包含图片描述
                }
            });

            if (!response.ok) {
                throw new Error('Failed to fetch content from Jina');
            }

            const data = await response.json();
            const content = data.data?.content || data.data?.text || '';
            const title = data.data?.title || '无标题';

            if (!content) {
                throw new Error('无法获取网页内容');
            }

            // 使用 Gemini 总结内容
            if (this.geminiApiKey) {
                return await this.summarizeWithGemini(title, content);
            }

            // 如果没有 Gemini，返回简单总结
            return {
                success: true,
                title: title,
                summary: this.createSimpleSummary(content),
                url: url
            };
        } catch (error) {
            console.error('Jina fetch error:', error);
            throw error;
        }
    }

    async summarizeWithJina(url) {
        // 使用付费 Jina API (如果有 key)
        try {
            const response = await fetch('https://api.jina.ai/v1/retrieve', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.jinaApiKey}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: url,
                    options: {
                        include_images: false,
                        include_raw_content: false
                    }
                })
            });

            if (!response.ok) {
                throw new Error('Jina API request failed');
            }

            const data = await response.json();
            return await this.summarizeWithGemini(data.title || '无标题', data.content || data.text);
        } catch (error) {
            // 降级到免费版本
            return await this.summarizeWithFreeJina(url);
        }
    }

    async summarizeWithGemini(title, content) {
        if (!this.geminiApiKey) {
            return {
                success: true,
                title: title,
                summary: this.createSimpleSummary(content),
                url: ''
            };
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
                            text: `请总结以下网页内容。要求：
1. 提取核心要点（3-5个）
2. 保持客观准确
3. 语言简洁清晰
4. 总结控制在200字以内

标题：${title}
内容：${content.substring(0, 3000)}...`
                        }]
                    }],
                    generationConfig: {
                        temperature: 0.5,
                        maxOutputTokens: 500
                    }
                })
            });

            if (!response.ok) {
                throw new Error('Gemini API request failed');
            }

            const data = await response.json();
            const summary = data.candidates?.[0]?.content?.parts?.[0]?.text || '总结失败';

            return {
                success: true,
                title: title,
                summary: summary,
                url: ''
            };
        } catch (error) {
            console.error('Gemini summarization error:', error);
            return {
                success: true,
                title: title,
                summary: this.createSimpleSummary(content),
                url: ''
            };
        }
    }

    createSimpleSummary(content) {
        // 简单的文本截取总结
        const cleanContent = content.replace(/\s+/g, ' ').trim();
        const sentences = cleanContent.match(/[^。！？.!?]+[。！？.!?]/g) || [];
        const summary = sentences.slice(0, 3).join(' ');
        return summary.substring(0, 200) + (summary.length > 200 ? '...' : '');
    }

    // 待办生成功能
    async generateTodos(noteText, noteId) {
        if (!this.geminiApiKey) {
            // 使用简单的正则提取待办
            return this.extractTodosSimple(noteText);
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
                            text: `从以下笔记中提取待办事项。要求：
1. 识别明确的任务和行动项
2. 每个待办事项简洁明了
3. 去除重复内容
4. 按优先级排序

笔记内容：${noteText}

请以JSON格式返回，格式如下：
{
  "todos": [
    {
      "text": "待办内容",
      "priority": "high/medium/low"
    }
  ]
}

只返回JSON，不要有其他内容。`
                        }]
                    }],
                    generationConfig: {
                        temperature: 0.3,
                        maxOutputTokens: 500,
                        responseMimeType: "application/json"
                    }
                })
            });

            if (!response.ok) {
                throw new Error('Gemini API request failed');
            }

            const data = await response.json();
            const responseText = data.candidates?.[0]?.content?.parts?.[0]?.text;
            
            if (responseText) {
                const result = JSON.parse(responseText);
                return {
                    success: true,
                    todos: result.todos || [],
                    sourceNoteId: noteId
                };
            }
        } catch (error) {
            console.error('Todo generation error:', error);
        }

        return this.extractTodosSimple(noteText);
    }

    extractTodosSimple(noteText) {
        const todos = [];
        const lines = noteText.split('\n');
        
        // 简单的待办识别规则
        const todoPatterns = [
            /^[-*]\s*(.+)$/,  // - 或 * 开头
            /^\d+\.\s*(.+)$/, // 数字列表
            /^TODO[:：]\s*(.+)$/i,
            /^待办[:：]\s*(.+)$/,
            /需要(.+)/,
            /计划(.+)/,
            /安排(.+)/
        ];

        lines.forEach(line => {
            for (const pattern of todoPatterns) {
                const match = line.match(pattern);
                if (match) {
                    todos.push({
                        text: match[1].trim(),
                        priority: 'medium'
                    });
                    break;
                }
            }
        });

        return {
            success: true,
            todos: todos.slice(0, 5), // 最多返回5个
            sourceNoteId: null
        };
    }

    // 笔记合并功能
    async mergeNotes(notes) {
        if (!notes || notes.length === 0) {
            throw new Error('没有选择要合并的笔记');
        }

        const combinedText = notes.map(note => note.text).join('\n\n');

        if (!this.geminiApiKey) {
            // 简单合并
            return {
                success: true,
                mergedText: this.simpleMergeNotes(notes),
                title: '合并的笔记',
                pills: this.extractAllPills(notes)
            };
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
                            text: `请将以下多条笔记智能合并成一篇完整的文章。要求：
1. 删除口语化词汇和重复内容
2. 保留所有重要信息
3. 修复错误的命名实体
4. 添加适当的二级、三级标题来组织内容
5. 保持逻辑连贯性
6. 使用 Markdown 格式

笔记内容：
${combinedText}

请直接返回合并后的文章内容，使用Markdown格式。`
                        }]
                    }],
                    generationConfig: {
                        temperature: 0.5,
                        maxOutputTokens: 2000
                    }
                })
            });

            if (!response.ok) {
                throw new Error('Gemini API request failed');
            }

            const data = await response.json();
            const mergedText = data.candidates?.[0]?.content?.parts?.[0]?.text || '';

            // 提取标题
            const titleMatch = mergedText.match(/^#\s+(.+)$/m);
            const title = titleMatch ? titleMatch[1] : '合并的笔记';

            return {
                success: true,
                mergedText: mergedText,
                title: title,
                pills: this.extractAllPills(notes)
            };
        } catch (error) {
            console.error('Note merge error:', error);
            return {
                success: true,
                mergedText: this.simpleMergeNotes(notes),
                title: '合并的笔记',
                pills: this.extractAllPills(notes)
            };
        }
    }

    simpleMergeNotes(notes) {
        // 简单的笔记合并逻辑
        let merged = '# 合并的笔记\n\n';
        
        notes.forEach((note, index) => {
            merged += `## 笔记 ${index + 1}\n\n`;
            merged += note.text + '\n\n';
        });

        return merged;
    }

    extractAllPills(notes) {
        const pillsMap = new Map();
        
        notes.forEach(note => {
            if (note.pills) {
                note.pills.forEach(pill => {
                    const key = `${pill.type}${pill.text}`;
                    if (!pillsMap.has(key)) {
                        pillsMap.set(key, pill);
                    }
                });
            }
        });

        return Array.from(pillsMap.values());
    }
}