// 简单的 TEN VAD 测试脚本
// 运行: 在浏览器控制台中执行

async function testTenVAD() {
    console.log('=== TEN VAD 测试开始 ===');
    
    try {
        // 1. 加载脚本
        console.log('1. 加载 ten_vad_loader.js...');
        await new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'public/ten_vad_loader.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
        
        // 2. 创建模块
        console.log('2. 创建 VAD 模块...');
        const vadModule = await createVADModule({
            locateFile: (filename) => {
                if (filename === 'ten_vad.wasm') {
                    return 'public/ten_vad.wasm';
                }
                return filename;
            }
        });
        
        // 3. 添加辅助函数
        vadModule.getValue = (ptr, type) => {
            switch (type) {
                case 'i32': return vadModule.HEAP32[ptr >> 2];
                case 'float': return vadModule.HEAPF32[ptr >> 2];
                default: throw new Error(`Unsupported type: ${type}`);
            }
        };
        
        // 4. 创建 VAD 实例
        console.log('3. 创建 VAD 实例...');
        const vadHandlePtr = vadModule._malloc(4);
        const result = vadModule._ten_vad_create(vadHandlePtr, 256, 0.5);
        
        if (result !== 0) {
            throw new Error(`VAD 创建失败: ${result}`);
        }
        
        const vadHandle = vadModule.getValue(vadHandlePtr, 'i32');
        console.log('VAD 实例创建成功，句柄:', vadHandle);
        
        // 5. 测试处理音频
        console.log('4. 测试音频处理...');
        const testAudio = new Int16Array(256);
        // 生成测试音频（440Hz 正弦波）
        for (let i = 0; i < 256; i++) {
            testAudio[i] = Math.sin(2 * Math.PI * 440 * i / 16000) * 8000;
        }
        
        const audioPtr = vadModule._malloc(256 * 2);
        const probPtr = vadModule._malloc(4);
        const flagPtr = vadModule._malloc(4);
        
        vadModule.HEAP16.set(testAudio, audioPtr / 2);
        
        const processResult = vadModule._ten_vad_process(
            vadHandle, audioPtr, 256, probPtr, flagPtr
        );
        
        if (processResult === 0) {
            const probability = vadModule.getValue(probPtr, 'float');
            const voiceFlag = vadModule.getValue(flagPtr, 'i32');
            console.log(`处理成功! 概率: ${probability}, 语音标志: ${voiceFlag}`);
        } else {
            console.error('处理失败:', processResult);
        }
        
        // 清理
        vadModule._free(audioPtr);
        vadModule._free(probPtr);
        vadModule._free(flagPtr);
        vadModule._ten_vad_destroy(vadHandlePtr);
        vadModule._free(vadHandlePtr);
        
        console.log('=== 测试完成 ===');
        return true;
        
    } catch (error) {
        console.error('测试失败:', error);
        return false;
    }
}

// 导出到全局
window.testTenVAD = testTenVAD;