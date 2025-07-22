export class VADManager {
    constructor() {
        this.audioContext = null;
        this.analyser = null;
        this.microphone = null;
        this.javascriptNode = null;
        this.isListening = false;
        this.isSpeaking = false;
        this.silenceTimer = null;
        this.listeners = {};
        this.smoothingBuffer = [];
        
        this.THRESHOLD = 15;
        this.SILENCE_DURATION = 1000;
        this.SMOOTHING_SAMPLES = 5;
        this.MIN_VOICE_DURATION = 300;
        this.voiceStartTime = null;
    }

    async start() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                } 
            });
            
            this.microphone = this.audioContext.createMediaStreamSource(stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.smoothingTimeConstant = 0.8;
            this.analyser.fftSize = 1024;
            
            this.javascriptNode = this.audioContext.createScriptProcessor(2048, 1, 1);
            this.javascriptNode.onaudioprocess = () => this.processAudio();
            
            this.microphone.connect(this.analyser);
            this.analyser.connect(this.javascriptNode);
            this.javascriptNode.connect(this.audioContext.destination);
            
            this.isListening = true;
        } catch (error) {
            console.error('VAD 初始化失败:', error);
            throw error;
        }
    }

    stop() {
        this.isListening = false;
        
        if (this.javascriptNode) {
            this.javascriptNode.disconnect();
        }
        if (this.microphone) {
            this.microphone.disconnect();
        }
        if (this.analyser) {
            this.analyser.disconnect();
        }
        if (this.audioContext) {
            this.audioContext.close();
        }
        
        if (this.silenceTimer) {
            clearTimeout(this.silenceTimer);
        }
    }

    processAudio() {
        if (!this.isListening) return;
        
        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        this.analyser.getByteFrequencyData(dataArray);
        
        // 关注人声频率范围 (300Hz - 3000Hz)
        const sampleRate = this.audioContext.sampleRate;
        const nyquist = sampleRate / 2;
        const binSize = nyquist / bufferLength;
        
        const minBin = Math.floor(300 / binSize);
        const maxBin = Math.floor(3000 / binSize);
        
        let voiceSum = 0;
        let voiceCount = 0;
        
        for (let i = minBin; i <= maxBin && i < bufferLength; i++) {
            voiceSum += dataArray[i];
            voiceCount++;
        }
        
        const voiceAverage = voiceCount > 0 ? voiceSum / voiceCount : 0;
        
        // 平滑处理
        this.smoothingBuffer.push(voiceAverage);
        if (this.smoothingBuffer.length > this.SMOOTHING_SAMPLES) {
            this.smoothingBuffer.shift();
        }
        
        const smoothedAverage = this.smoothingBuffer.reduce((a, b) => a + b, 0) / this.smoothingBuffer.length;
        
        if (smoothedAverage > this.THRESHOLD) {
            if (!this.isSpeaking) {
                this.voiceStartTime = Date.now();
                this.isSpeaking = true;
                this.emit('speechStart');
            }
            
            if (this.silenceTimer) {
                clearTimeout(this.silenceTimer);
                this.silenceTimer = null;
            }
        } else if (this.isSpeaking && !this.silenceTimer) {
            const voiceDuration = Date.now() - this.voiceStartTime;
            
            if (voiceDuration >= this.MIN_VOICE_DURATION) {
                this.silenceTimer = setTimeout(() => {
                    this.isSpeaking = false;
                    this.emit('speechEnd');
                    this.silenceTimer = null;
                }, this.SILENCE_DURATION);
            } else {
                this.isSpeaking = false;
            }
        }
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