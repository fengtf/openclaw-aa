#!/usr/bin/env python3
"""
FunASR WebSocket 完整测试脚本
测试实时音频流式传输识别
"""

import asyncio
import websockets
import json
import soundfile as sf
import numpy as np
from pathlib import Path
import time
import sys


class TestWebSocket:
    def __init__(self, uri="ws://localhost:10095/ws/asr"):
        self.uri = uri

    async def test_connection(self):
        """测试基本连接"""
        print("\n1. 测试WebSocket连接...")
        try:
            async with websockets.connect(self.uri) as websocket:
                # 接收欢迎消息
                welcome = await websocket.recv()
                data = json.loads(welcome)
                print(f"   ✅ 连接成功")
                print(f"      服务器消息: {data.get('message')}")
                return True
        except Exception as e:
            print(f"   ❌ 连接失败: {e}")
            return False

    async def test_audio_recognition(self, audio_path, chunk_size=32000):
        """
        测试音频识别
        chunk_size: 每个chunk的字节数 (16kHz, 16bit PCM, 1秒=32000字节)
        """
        print(f"\n2. 测试音频识别...")
        print(f"   音频文件: {Path(audio_path).name}")

        try:
            # 读取音频
            audio, sr = sf.read(audio_path)

            # 转换为16bit PCM
            if audio.dtype == np.float32 or audio.dtype == np.float64:
                audio_int16 = (audio * 32767).astype(np.int16)
            else:
                audio_int16 = audio.astype(np.int16)

            audio_bytes = audio_int16.tobytes()

            async with websockets.connect(self.uri) as websocket:
                # 接收欢迎消息
                welcome = await websocket.recv()

                # 发送音频数据
                total_chunks = len(audio_bytes) // chunk_size + 1
                print(f"   开始发送音频数据, 总大小: {len(audio_bytes)/1024:.1f}KB, 块数: {total_chunks}")

                start_time = time.time()

                for i in range(0, len(audio_bytes), chunk_size):
                    chunk = audio_bytes[i:i + chunk_size]
                    await websocket.send(chunk)

                    # 接收进度反馈（非阻塞）
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                        data = json.loads(response)
                        if data.get('type') == 'progress':
                            print(f"   进度: {data.get('message')}", end='\r')
                    except asyncio.TimeoutError:
                        pass

                print("\n   音频发送完成，发送结束命令...")

                # 发送结束命令
                await websocket.send(json.dumps({"action": "end"}))

                # 接收识别结果（可能先收到 processing 消息）
                result = None
                while True:
                    response = await websocket.recv()
                    data = json.loads(response)
                    if data.get('type') == 'processing':
                        print("   服务器处理中...")
                        continue
                    if 'success' in data or 'error' in data:
                        result = data
                        break

                elapsed = time.time() - start_time

                if result and result.get('success'):
                    print(f"\n   ✅ 识别成功! 耗时: {elapsed:.2f}秒")
                    print(f"\n   识别结果:")
                    print(f"   {'='*50}")
                    print(f"   {result['text']}")
                    print(f"   {'='*50}")

                    # 保存结果到文件
                    output_file = f"result_{Path(audio_path).stem}.txt"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(result['text'])
                    print(f"\n   结果已保存到: {output_file}")

                    return True
                else:
                    print(f"   ❌ 识别失败: {result.get('error') if result else '未知错误'}")
                    return False

        except Exception as e:
            print(f"   ❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def test_concurrent_connections(self, audio_path, num_clients=3):
        """测试并发连接"""
        print(f"\n3. 测试并发连接 ({num_clients}个客户端)...")

        async def client_task(client_id):
            try:
                async with websockets.connect(self.uri) as websocket:
                    # 接收欢迎消息
                    await websocket.recv()

                    # 发送测试音频的一小部分
                    audio, sr = sf.read(audio_path)
                    if audio.dtype == np.float32 or audio.dtype == np.float64:
                        audio_int16 = (audio[:sr] * 32767).astype(np.int16)  # 只发送1秒
                    else:
                        audio_int16 = audio[:sr].astype(np.int16)

                    await websocket.send(audio_int16.tobytes())
                    await websocket.send(json.dumps({"action": "end"}))

                    # 接收结果
                    while True:
                        response = await websocket.recv()
                        data = json.loads(response)
                        if 'success' in data or 'error' in data:
                            return True
            except Exception as e:
                print(f"   客户端{client_id}失败: {e}")
                return False

        # 并发执行多个客户端
        tasks = [client_task(i) for i in range(num_clients)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        print(f"   并发测试结果: {success_count}/{num_clients} 成功")
        return success_count == num_clients

    async def run_all_tests(self, audio_file):
        """运行所有WebSocket测试"""
        print("="*60)
        print("   FunASR WebSocket 完整测试")
        print("="*60)

        if not Path(audio_file).exists():
            print(f"❌ 测试音频不存在: {audio_file}")
            return

        # 运行测试
        results = await asyncio.gather(
            self.test_connection(),
            self.test_audio_recognition(audio_file),
            self.test_concurrent_connections(audio_file, 3)
        )

        print("\n" + "="*60)
        print(f"   WebSocket测试完成")
        print(f"   连接测试: {'✅' if results[0] else '❌'}")
        print(f"   识别测试: {'✅' if results[1] else '❌'}")
        print(f"   并发测试: {'✅' if results[2] else '❌'}")
        print("="*60)


async def main():
    audio_file = sys.argv[1] if len(sys.argv) > 1 else "test_zh.wav"

    tester = TestWebSocket()
    await tester.run_all_tests(audio_file)


if __name__ == "__main__":
    asyncio.run(main())
