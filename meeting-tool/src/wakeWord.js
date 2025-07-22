export class WakeWordDetector {
    constructor() {
        this.listeners = {};
        this.wakeWords = ['小爱同学', '小爱', 'xiaoi'];
        this.lastDetectionTime = 0;
        this.cooldownPeriod = 3000; // 3秒冷却时间
    }

    detect(text) {
        const currentTime = Date.now();
        
        // 检查冷却时间
        if (currentTime - this.lastDetectionTime < this.cooldownPeriod) {
            return false;
        }

        const lowerText = text.toLowerCase();
        
        for (const wakeWord of this.wakeWords) {
            if (text.includes(wakeWord) || lowerText.includes(wakeWord.toLowerCase())) {
                this.lastDetectionTime = currentTime;
                this.emit('wakeWordDetected', {
                    wakeWord: wakeWord,
                    text: text,
                    timestamp: currentTime
                });
                return true;
            }
        }
        
        return false;
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