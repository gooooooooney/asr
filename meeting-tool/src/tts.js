export class TTSManager {
    constructor() {
        this.synthesis = window.speechSynthesis;
        this.voice = null;
        this.rate = 1.0;
        this.pitch = 1.0;
        this.volume = 1.0;
        
        this.loadVoices();
    }

    loadVoices() {
        const loadVoicesHandler = () => {
            const voices = this.synthesis.getVoices();
            const zhVoice = voices.find(voice => voice.lang.includes('zh'));
            if (zhVoice) {
                this.voice = zhVoice;
            }
        };

        loadVoicesHandler();
        if (this.synthesis.onvoiceschanged !== undefined) {
            this.synthesis.onvoiceschanged = loadVoicesHandler;
        }
    }

    async speak(text) {
        return new Promise((resolve, reject) => {
            if (!this.synthesis) {
                reject(new Error('浏览器不支持语音合成'));
                return;
            }

            this.synthesis.cancel();

            const utterance = new SpeechSynthesisUtterance(text);
            
            if (this.voice) {
                utterance.voice = this.voice;
            }
            
            utterance.lang = 'zh-CN';
            utterance.rate = this.rate;
            utterance.pitch = this.pitch;
            utterance.volume = this.volume;
            
            utterance.onend = () => {
                resolve();
            };
            
            utterance.onerror = (event) => {
                console.error('TTS 错误:', event);
                reject(new Error('语音合成失败'));
            };
            
            this.synthesis.speak(utterance);
        });
    }

    stop() {
        if (this.synthesis) {
            this.synthesis.cancel();
        }
    }

    pause() {
        if (this.synthesis) {
            this.synthesis.pause();
        }
    }

    resume() {
        if (this.synthesis) {
            this.synthesis.resume();
        }
    }
}