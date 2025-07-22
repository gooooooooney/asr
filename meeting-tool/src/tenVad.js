export class TenVADManager {
    constructor() {
        this.audioContext = null;
        this.microphone = null;
        this.scriptProcessor = null;
        this.isListening = false;
        this.listeners = {};
        
        // TEN VAD specific
        this.vadModule = null;
        this.vadHandle = null;
        this.vadHandlePtr = null;
        
        // Configuration
        this.HOP_SIZE = 256; // 16ms per frame at 16kHz
        this.THRESHOLD = 0.5;
        this.sampleRate = 16000;
        
        // Buffer for audio processing
        this.audioBuffer = [];
        this.isSpeaking = false;
        this.speechStartTime = null;
        this.silenceStartTime = null;
        this.SILENCE_DURATION = 800; // ms
    }

    async loadVADModule() {
        try {
            return new Promise((resolve, reject) => {
                // Check if ten_vad_loader.js already loaded
                if (typeof createVADModule !== 'undefined') {
                    this.initializeVAD(resolve, reject);
                    return;
                }
                
                // Try to load the VAD loader script
                const script = document.createElement('script');
                script.src = 'meeting-tool/public/ten_vad_loader.js';
                
                script.onload = () => {
                    console.log('TEN VAD loader script loaded');
                    this.initializeVAD(resolve, reject);
                };
                
                script.onerror = (error) => {
                    console.error('Failed to load ten_vad_loader.js:', error);
                    reject(new Error('Failed to load ten_vad.js'));
                };
                
                document.head.appendChild(script);
            });
        } catch (error) {
            console.error('Failed to load TEN VAD module:', error);
            throw error;
        }
    }
    
    async initializeVAD(resolve, reject) {
        try {
            if (typeof createVADModule !== 'undefined') {
                // Real implementation
                this.vadModule = await createVADModule({
                    locateFile: (filename) => {
                        if (filename === 'ten_vad.wasm') {
                            return 'meeting-tool/public/ten_vad.wasm';
                        }
                        return filename;
                    }
                });
                
                // Add helper functions if not present
                this.addHelperFunctions();
                
                console.log('TEN VAD module initialized successfully');
                resolve();
            } else {
                reject(new Error('createVADModule is not defined'));
            }
        } catch (error) {
            console.error('Failed to initialize VAD:', error);
            reject(error);
        }
    }

    addHelperFunctions() {
        if (!this.vadModule.getValue) {
            this.vadModule.getValue = (ptr, type) => {
                switch (type) {
                    case 'i32': return this.vadModule.HEAP32[ptr >> 2];
                    case 'float': return this.vadModule.HEAPF32[ptr >> 2];
                    default: throw new Error(`Unsupported type: ${type}`);
                }
            };
        }
        
        if (!this.vadModule.UTF8ToString) {
            this.vadModule.UTF8ToString = (ptr) => {
                if (!ptr) return '';
                let result = '';
                let i = ptr;
                while (this.vadModule.HEAPU8[i]) {
                    result += String.fromCharCode(this.vadModule.HEAPU8[i++]);
                }
                return result;
            };
        }
    }

    createVADInstance() {
        try {
            // Check if using mock implementation
            if (this.vadModule.start) {
                console.log('Using mock VAD instance');
                return true;
            }
            
            // Real implementation
            this.vadHandlePtr = this.vadModule._malloc(4);
            const result = this.vadModule._ten_vad_create(
                this.vadHandlePtr, 
                this.HOP_SIZE, 
                this.THRESHOLD
            );
            
            if (result === 0) {
                this.vadHandle = this.vadModule.getValue(this.vadHandlePtr, 'i32');
                console.log('TEN VAD instance created successfully');
                return true;
            } else {
                console.error('VAD creation failed with code:', result);
                this.vadModule._free(this.vadHandlePtr);
                return false;
            }
        } catch (error) {
            console.error('Error creating VAD instance:', error);
            return false;
        }
    }

    destroyVADInstance() {
        if (this.vadHandlePtr && this.vadModule) {
            this.vadModule._ten_vad_destroy(this.vadHandlePtr);
            this.vadModule._free(this.vadHandlePtr);
            this.vadHandlePtr = null;
            this.vadHandle = null;
        }
    }

    async start() {
        try {
            // Load VAD module if not loaded
            if (!this.vadModule) {
                await this.loadVADModule();
            }
            
            // Check if using mock implementation
            if (this.vadModule.start) {
                // Mock implementation - just start it
                this.isListening = true;
                await this.vadModule.start();
                console.log('Mock TEN VAD started');
                return;
            }
            
            // Create VAD instance for real implementation
            if (!this.createVADInstance()) {
                throw new Error('Failed to create VAD instance');
            }
            
            // Initialize audio context
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.sampleRate
            });
            
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                    sampleRate: this.sampleRate
                } 
            });
            
            this.microphone = this.audioContext.createMediaStreamSource(stream);
            
            // Use ScriptProcessorNode for audio processing
            this.scriptProcessor = this.audioContext.createScriptProcessor(
                this.HOP_SIZE * 2, // Buffer size
                1, // Input channels
                1  // Output channels
            );
            
            this.scriptProcessor.onaudioprocess = (e) => {
                if (this.isListening) {
                    this.processAudio(e.inputBuffer);
                }
            };
            
            this.microphone.connect(this.scriptProcessor);
            this.scriptProcessor.connect(this.audioContext.destination);
            
            this.isListening = true;
            console.log('TEN VAD started');
        } catch (error) {
            console.error('VAD 初始化失败:', error);
            throw error;
        }
    }

    processAudio(audioBuffer) {
        const channelData = audioBuffer.getChannelData(0);
        
        // Convert float32 to int16
        const int16Data = new Int16Array(channelData.length);
        for (let i = 0; i < channelData.length; i++) {
            const s = Math.max(-1, Math.min(1, channelData[i]));
            int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        
        // Add to buffer
        this.audioBuffer.push(...int16Data);
        
        // Process when we have enough samples
        while (this.audioBuffer.length >= this.HOP_SIZE) {
            const frameData = new Int16Array(this.audioBuffer.splice(0, this.HOP_SIZE));
            this.processFrame(frameData);
        }
    }

    processFrame(frameData) {
        if (!this.vadHandle || !this.vadModule) return;
        
        const audioPtr = this.vadModule._malloc(this.HOP_SIZE * 2);
        const probPtr = this.vadModule._malloc(4);
        const flagPtr = this.vadModule._malloc(4);
        
        try {
            // Copy audio data to WASM memory
            this.vadModule.HEAP16.set(frameData, audioPtr / 2);
            
            // Process with TEN VAD
            const result = this.vadModule._ten_vad_process(
                this.vadHandle,
                audioPtr,
                this.HOP_SIZE,
                probPtr,
                flagPtr
            );
            
            if (result === 0) {
                const probability = this.vadModule.getValue(probPtr, 'float');
                const voiceFlag = this.vadModule.getValue(flagPtr, 'i32');
                
                this.handleVADResult(voiceFlag === 1, probability);
            }
        } finally {
            this.vadModule._free(audioPtr);
            this.vadModule._free(probPtr);
            this.vadModule._free(flagPtr);
        }
    }

    handleVADResult(isVoice, probability) {
        const currentTime = Date.now();
        
        if (isVoice && !this.isSpeaking) {
            // Speech started
            this.isSpeaking = true;
            this.speechStartTime = currentTime;
            this.silenceStartTime = null;
            this.emit('speechStart', { probability });
        } else if (!isVoice && this.isSpeaking) {
            // Potential speech end
            if (!this.silenceStartTime) {
                this.silenceStartTime = currentTime;
            } else if (currentTime - this.silenceStartTime > this.SILENCE_DURATION) {
                // Confirmed speech end
                this.isSpeaking = false;
                this.emit('speechEnd', { 
                    duration: this.silenceStartTime - this.speechStartTime,
                    probability 
                });
                this.silenceStartTime = null;
            }
        } else if (isVoice && this.silenceStartTime) {
            // Speech resumed, cancel silence timer
            this.silenceStartTime = null;
        }
    }

    stop() {
        this.isListening = false;
        
        // Check if using mock implementation
        if (this.vadModule && this.vadModule.stop) {
            this.vadModule.stop();
            console.log('Mock TEN VAD stopped');
            return;
        }
        
        // Real implementation cleanup
        if (this.scriptProcessor) {
            this.scriptProcessor.disconnect();
            this.scriptProcessor = null;
        }
        
        if (this.microphone) {
            this.microphone.disconnect();
            this.microphone = null;
        }
        
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        this.destroyVADInstance();
        
        // Clear buffers
        this.audioBuffer = [];
        this.isSpeaking = false;
        
        console.log('TEN VAD stopped');
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