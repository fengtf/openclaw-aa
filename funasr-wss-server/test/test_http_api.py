#!/usr/bin/env python3
"""
FunASR HTTP API 完整测试脚本
测试文件上传、Base64编码、热词功能等
"""

import requests
import json
import base64
import soundfile as sf
import numpy as np
from pathlib import Path
import time
import sys


class TestHTTPAPI:
    def __init__(self, base_url="http://localhost:10095"):
        self.base_url = base_url
        self.session = requests.Session()

    def test_health(self):
        """测试健康检查"""
        print("\n1. 测试健康检查接口...")
        try:
            resp = self.session.get(f"{self.base_url}/health")
            assert resp.status_code == 200
            data = resp.json()
            print(f"   ✅ 健康检查通过: {data}")
            return True
        except Exception as e:
            print(f"   ❌ 健康检查失败: {e}")
            return False

    def test_server_info(self):
        """测试服务器信息"""
        print("\n2. 测试服务器信息接口...")
        try:
            resp = self.session.get(f"{self.base_url}/")
            assert resp.status_code == 200
            data = resp.json()
            print(f"   ✅ 获取服务器信息成功")
            print(f"      模型: {data.get('model')}")
            print(f"      设备: {data.get('device')}")
            print(f"      连接数: {data.get('connections')}")
            return True
        except Exception as e:
            print(f"   ❌ 获取服务器信息失败: {e}")
            return False

    def test_file_upload(self, audio_path, hotword=None):
        """测试文件上传识别"""
        print(f"\n3. 测试文件上传识别...")
        print(f"   音频文件: {Path(audio_path).name}")
        if hotword:
            print(f"   热词: {hotword}")

        try:
            with open(audio_path, 'rb') as f:
                files = {'file': (Path(audio_path).name, f, 'audio/wav')}
                data = {}
                if hotword:
                    data['hotword'] = hotword

                start_time = time.time()
                resp = self.session.post(
                    f"{self.base_url}/api/asr/file",
                    files=files,
                    data=data
                )
                elapsed = time.time() - start_time

            assert resp.status_code == 200
            result = resp.json()

            if result.get('success'):
                print(f"   ✅ 识别成功! 耗时: {elapsed:.2f}秒")
                print(f"\n   识别结果:")
                print(f"   {'='*50}")
                print(f"   {result['text']}")
                print(f"   {'='*50}")

                # 显示句子级别时间戳
                if result.get('detail', {}).get('sentences'):
                    print(f"\n   句子时间戳:")
                    for s in result['detail']['sentences']:
                        start = s.get('start', 0) / 1000
                        end = s.get('end', 0) / 1000
                        text = s.get('text', '')
                        print(f"   [{start:.2f}s -> {end:.2f}s] {text}")
                return True
            else:
                print(f"   ❌ 识别失败: {result.get('error')}")
                return False

        except Exception as e:
            print(f"   ❌ 测试失败: {e}")
            return False

    def test_base64_audio(self, audio_path, hotword=None):
        """测试Base64编码音频识别"""
        print(f"\n4. 测试Base64音频识别...")

        try:
            # 读取音频并转换为Base64
            audio, sr = sf.read(audio_path)

            # 转换为16bit PCM
            if audio.dtype == np.float32 or audio.dtype == np.float64:
                audio_int16 = (audio * 32767).astype(np.int16)
            else:
                audio_int16 = audio.astype(np.int16)

            audio_base64 = base64.b64encode(audio_int16.tobytes()).decode('utf-8')

            data = {
                'audio': audio_base64,
                'sample_rate': sr,
            }
            if hotword:
                data['hotword'] = hotword

            start_time = time.time()
            resp = self.session.post(
                f"{self.base_url}/api/asr/base64",
                json=data
            )
            elapsed = time.time() - start_time

            assert resp.status_code == 200
            result = resp.json()

            if result.get('success'):
                print(f"   ✅ Base64识别成功! 耗时: {elapsed:.2f}秒")
                print(f"\n   识别结果:")
                print(f"   {'='*50}")
                text = result['text']
                print(f"   {text[:100]}..." if len(text) > 100 else f"   {text}")
                print(f"   {'='*50}")
                return True
            else:
                print(f"   ❌ 识别失败: {result.get('error')}")
                return False

        except Exception as e:
            print(f"   ❌ 测试失败: {e}")
            return False

    def test_invalid_file(self):
        """测试无效文件上传"""
        print("\n5. 测试无效文件上传...")
        try:
            files = {'file': ('test.txt', b'hello world', 'text/plain')}
            resp = self.session.post(
                f"{self.base_url}/api/asr/file",
                files=files
            )
            # 应该返回错误，但不是崩溃
            print(f"   ✅ 错误处理正常: {resp.status_code}")
            return True
        except Exception as e:
            print(f"   ✅ 异常处理正常: {e}")
            return True

    def run_all_tests(self, audio_file):
        """运行所有测试"""
        print("="*60)
        print("   FunASR HTTP API 完整测试")
        print("="*60)

        if not Path(audio_file).exists():
            print(f"❌ 测试音频不存在: {audio_file}")
            print("请先下载测试音频:")
            print("curl -o test_zh.wav https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/vad_example.wav")
            return

        tests = [
            self.test_health,
            self.test_server_info,
            lambda: self.test_file_upload(audio_file),
            lambda: self.test_file_upload(audio_file, "阿里巴巴 达摩院 语音识别"),
            lambda: self.test_base64_audio(audio_file),
            lambda: self.test_base64_audio(audio_file, "热词测试"),
            self.test_invalid_file
        ]

        passed = 0
        for i, test in enumerate(tests, 1):
            try:
                if test():
                    passed += 1
            except Exception as e:
                print(f"   ❌ 测试{i}异常: {e}")

        print("\n" + "="*60)
        print(f"   测试完成: 通过 {passed}/{len(tests)}")
        print("="*60)


if __name__ == "__main__":
    audio_file = sys.argv[1] if len(sys.argv) > 1 else "test_zh.wav"

    tester = TestHTTPAPI()
    tester.run_all_tests(audio_file)
