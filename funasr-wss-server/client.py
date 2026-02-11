import asyncio
import json
import logging
import soundfile as sf
import websockets
from pathlib import Path
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ASRClient:
    def __init__(self, server_url: str = "ws://localhost:10095/ws/asr"):
        self.server_url = server_url
        self.chunk_duration_ms = 600
        self.sample_rate = 16000
        self.chunk_samples = int(self.sample_rate * self.chunk_duration_ms / 1000)
    
    async def stream_audio_file(self, audio_path: str):
        """流式传输音频文件到ASR服务器"""
        try:
            audio, sr = sf.read(audio_path)
            
            if sr != self.sample_rate:
                logger.warning(f"音频采样率 {sr} 与服务器期望的 {self.sample_rate} 不匹配")
            
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            audio_int16 = (audio * 32767).astype(np.int16)
            
            async with websockets.connect(self.server_url) as websocket:
                logger.info(f"已连接到服务器 {self.server_url}")
                
                for i in range(0, len(audio_int16), self.chunk_samples):
                    chunk = audio_int16[i:i + self.chunk_samples]
                    
                    if len(chunk) < self.chunk_samples:
                        padding = np.zeros(self.chunk_samples - len(chunk), dtype=np.int16)
                        chunk = np.concatenate([chunk, padding])
                    
                    await websocket.send(chunk.tobytes())
                    
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        result = json.loads(response)
                        
                        if 'text' in result and result['text']:
                            print(f"识别结果: {result['text']}")
                        elif 'error' in result:
                            logger.error(f"服务器返回错误: {result['error']}")
                    
                    except asyncio.TimeoutError:
                        continue
                
                await websocket.send(json.dumps({"action": "end"}))
                
                try:
                    final_response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    print(f"最终结果: {final_response}")
                except asyncio.TimeoutError:
                    pass
        
        except Exception as e:
            logger.error(f"客户端错误: {e}")
    
    async def realtime_microphone(self):
        """实时麦克风输入（需要安装pyaudio）"""
        try:
            import pyaudio
            
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_samples
            )
            
            async with websockets.connect(self.server_url) as websocket:
                logger.info("开始实时语音识别，按Ctrl+C停止...")
                
                try:
                    while True:
                        data = stream.read(self.chunk_samples, exception_on_overflow=False)
                        await websocket.send(data)
                        
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                            result = json.loads(response)
                            
                            if 'text' in result and result['text']:
                                print(f"实时结果: {result['text']}")
                        
                        except asyncio.TimeoutError:
                            continue
                
                except KeyboardInterrupt:
                    logger.info("停止实时识别")
                
                finally:
                    stream.stop_stream()
                    stream.close()
                    p.terminate()
        
        except ImportError:
            logger.error("请先安装 pyaudio: pip install pyaudio")
        except Exception as e:
            logger.error(f"实时麦克风错误: {e}")


async def main():
    client = ASRClient()
    
    print("FunASR WebSocket客户端")
    print("1. 流式传输音频文件")
    print("2. 实时麦克风输入")
    
    choice = input("请选择模式 (1/2): ").strip()
    
    if choice == "1":
        audio_path = input("请输入音频文件路径: ").strip()
        if Path(audio_path).exists():
            await client.stream_audio_file(audio_path)
        else:
            print("文件不存在")
    
    elif choice == "2":
        await client.realtime_microphone()
    
    else:
        print("无效选择")


if __name__ == "__main__":
    asyncio.run(main())
