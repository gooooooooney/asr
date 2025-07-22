// Mock implementation of TEN VAD for testing
// In production, this would be the actual TEN VAD library

class TENVAD {
    constructor() {
        this.onSpeechStart = null;
        this.onSpeechEnd = null;
        this.isListening = false;
        this.lastSpeechTime = 0;
        this.silenceThreshold = 1500; // 1.5 seconds
        this.checkInterval = null;
    }

    start() {
        console.log('[TEN VAD] Starting voice activity detection (mock)');
        this.isListening = true;
        this.lastSpeechTime = Date.now();
        
        // Simulate VAD by checking audio levels periodically
        this.checkInterval = setInterval(() => {
            if (!this.isListening) return;
            
            // Mock logic: randomly simulate speech activity
            const isSpeaking = Math.random() > 0.7;
            const now = Date.now();
            
            if (isSpeaking) {
                if (now - this.lastSpeechTime > this.silenceThreshold) {
                    // Speech started after silence
                    if (this.onSpeechStart) {
                        console.log('[TEN VAD] Speech detected');
                        this.onSpeechStart();
                    }
                }
                this.lastSpeechTime = now;
            } else {
                if (now - this.lastSpeechTime > this.silenceThreshold) {
                    // Silence detected
                    if (this.onSpeechEnd) {
                        console.log('[TEN VAD] Silence detected');
                        this.onSpeechEnd();
                    }
                    this.lastSpeechTime = now + this.silenceThreshold; // Prevent repeated triggers
                }
            }
        }, 100);
        
        return Promise.resolve();
    }

    stop() {
        console.log('[TEN VAD] Stopping voice activity detection');
        this.isListening = false;
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
            this.checkInterval = null;
        }
    }

    setOnSpeechStart(callback) {
        this.onSpeechStart = callback;
    }

    setOnSpeechEnd(callback) {
        this.onSpeechEnd = callback;
    }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TENVAD;
} else {
    window.TENVAD = TENVAD;
}

console.log('[TEN VAD] Library loaded successfully');