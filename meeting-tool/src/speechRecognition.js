export class SpeechRecognitionManager {
    constructor() {
        this.recognition = null;
        this.isListening = false;
        this.fullTranscript = '';
        this.listeners = {};
        
        this.initializeSpeechRecognition();
    }

    initializeSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (!SpeechRecognition) {
            throw new Error('浏览器不支持 Web Speech API');
        }

        this.recognition = new SpeechRecognition();
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = 'zh-CN';
        
        this.recognition.onresult = (event) => this.handleResult(event);
        this.recognition.onerror = (event) => this.handleError(event);
        this.recognition.onend = () => this.handleEnd();
    }

    start() {
        if (!this.isListening) {
            this.isListening = true;
            this.fullTranscript = '';
            this.recognition.start();
        }
    }

    stop() {
        if (this.isListening) {
            this.isListening = false;
            this.recognition.stop();
        }
    }

    handleResult(event) {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += transcript;
            } else {
                interimTranscript += transcript;
            }
        }

        if (finalTranscript) {
            this.fullTranscript += finalTranscript;
        }

        const currentTranscript = this.fullTranscript + interimTranscript;
        this.emit('transcript', currentTranscript);
    }

    handleError(event) {
        console.error('语音识别错误:', event.error);
        this.emit('error', new Error(`语音识别错误: ${event.error}`));
        
        if (event.error === 'no-speech') {
            this.restart();
        }
    }

    handleEnd() {
        if (this.isListening) {
            this.restart();
        }
    }

    restart() {
        setTimeout(() => {
            if (this.isListening) {
                this.recognition.start();
            }
        }, 100);
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