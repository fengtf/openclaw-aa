import asyncio
import json
import logging
import soundfile as sf
import websockets
import base64
from pathlib import Path
import numpy as np
import requests
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ParaformerClient:
    """Paraformer-zh 模型客户端"""
    
    def __init__(self, server_url: str = "ws://localhost:10095/ws/asr", http_url: str = "http://localhost:10095"):
        self.ws_url = server_url
        self.http_url = http_url
        self.sample_rate = 16000
    
    async def recognize_file_websocket(self, audio_path: str):
        """通过WebSocket发送完整音频文件"""
        try:
            # 读取音频文件
            audio, sr = sf.read(audio_path)
            
            # 转换为16kHz单声道
            if sr != self.sample_rate:
                logger.warning(f"采样率 {sr}Hz 转换为 {self.sample_rate}Hz")
                # 这里可以添加重采样逻辑
            
            # 转换为16bit PCM
            if audio.dtype == np.float32 or audio.dtype == np.float64:
                audio_int16 = (audio * 32767).astype(np.int16)
            else:
                audio_int16 = audio.astype(np.int16)
            
            async with websockets.connect(self.ws_url) as websocket:
                logger.info(f"已连接到服务器: {self.ws_url}")
                
                # 接收欢迎消息
                welcome = await websocket.recv()
                print(f"服务器: {json.loads(welcome)['message']}")
                
                # 发送音频数据
                audio_bytes = audio_int16.tobytes()
                chunk_size = 16000 * 2  # 2秒一个chunk，避免消息过大
                
                for i in range(0, len(audio_bytes), chunk_size):
                    chunk = audio_bytes[i:i + chunk_size]
                    await websocket.send(chunk)
                    print(f"发送音频数据: {i/1024:.0f}KB / {len(audio_bytes)/1024:.0f}KB", end='\r')
                
                print("\n音频发送完成，等待识别...")
                
                # 发送结束命令
                await websocket.send(json.dumps({"action": "end"}))
                
                # 接收识别结果
                response = await websocket.recv()
                result = json.loads(response)
                
                if result.get('success'):
                    print("\n" + "="*60)
                    print("识别结果:")
                    print("="*60)
                    print(f"{result['text']}")
                    print("="*60)
                    
                    # 显示详细信息
                    if result.get('detail', {}).get('sentences'):
                        print("\n句子级别时间戳:")
                        for s in result['detail']['sentences']:
                            start = s.get('start', 0) / 1000
                            end = s.get('end', 0) / 1000
                            text = s.get('text', '')
                            print(f"[{start:.2f}s -> {end:.2f}s] {text}")
                else:
                    print(f"识别失败: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"识别失败: {e}")
    
    def recognize_file_http(self, audio_path: str, hotword: str = None):
        """通过HTTP上传文件识别"""
        try:
            url = f"{self.http_url}/api/asr/file"
            
            with open(audio_path, 'rb') as f:
                files = {'file': (Path(audio_path).name, f, 'audio/wav')}
                data = {}
                if hotword:
                    data['hotword'] = hotword
                
                response = requests.post(url, files=files, data=data)
                result = response.json()
                
                if result.get('success'):
                    print("\n" + "="*60)
                    print("HTTP识别结果:")
                    print("="*60)
                    print(f"{result['text']}")
                    print("="*60)
                else:
                    print(f"识别失败: {result.get('error')}")
                    
        except Exception as e:
            logger.error(f"HTTP识别失败: {e}")
    
    def recognize_base64(self, audio_path: str, hotword: str = None):
        """通过Base64编码识别"""
        try:
            url = f"{self.http_url}/api/asr/base64"
            
            # 读取音频并转换为base64
            audio, sr = sf.read(audio_path)
            if audio.dtype == np.float32 or audio.dtype == np.float64:
                audio_int16 = (audio * 32767).astype(np.int16)
            else:
                audio_int16 = audio.astype(np.int16)
            
            audio_base64 = base64.b64encode(audio_int16.tobytes()).decode('utf-8')
            
            data = {
                'audio': audio_base64,
                'sample_rate': sr,
                'hotword': hotword
            }
            
            response = requests.post(url, json=data)
            result = response.json()
            
            if result.get('success'):
                print("\n" + "="*60)
                print("Base64识别结果:")
                print("="*60)
                print(f"{result['text']}")
                print("="*60)
            else:
                print(f"识别失败: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Base64识别失败: {e}")

async def main():
    parser = argparse.ArgumentParser(description='FunASR Paraformer-zh 客户端')
    parser.add_argument('audio_file', help='音频文件路径')
    parser.add_argument('--hotword', help='热词，多个热词用空格分隔')
    parser.add_argument('--mode', choices=['websocket', 'http', 'base64'], 
                       default='websocket', help='识别模式')
    parser.add_argument('--server', default='ws://localhost:10095/ws/asr', 
                       help='WebSocket服务器地址')
    parser.add_argument('--http', default='http://localhost:10095', 
                       help='HTTP服务器地址')
    
    args = parser.parse_args()
    
    client = ParaformerClient(args.server, args.http)
    
    if not Path(args.audio_file).exists():
        print(f"文件不存在: {args.audio_file}")
        return
    
    print(f"\n开始识别: {args.audio_file}")
    print(f"模式: {args.mode}")
    if args.hotword:
        print(f"热词: {args.hotword}")
    print("-" * 60)
    
    if args.mode == 'websocket':
        await client.recognize_file_websocket(args.audio_file)
    elif args.mode == 'http':
        client.recognize_file_http(args.audio_file, args.hotword)
    else:  # base64
        client.recognize_base64(args.audio_file, args.hotword)

if __name__ == "__main__":
    asyncio.run(main())
