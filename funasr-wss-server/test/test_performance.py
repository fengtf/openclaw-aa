#!/usr/bin/env python3
"""
FunASR 性能压力测试脚本
测试并发处理能力和RTF(实时率)
"""

import requests
import concurrent.futures
import time
import statistics
from pathlib import Path
import sys
import json


class PerformanceTest:
    def __init__(self, base_url="http://localhost:10095"):
        self.base_url = base_url

    def test_single_recognition(self, audio_path, hotword=None):
        """单次识别性能测试"""
        with open(audio_path, 'rb') as f:
            files = {'file': (Path(audio_path).name, f, 'audio/wav')}
            data = {'hotword': hotword} if hotword else {}

            start_time = time.time()
            resp = requests.post(f"{self.base_url}/api/asr/file", files=files, data=data)
            elapsed = time.time() - start_time

            return {
                'success': resp.status_code == 200,
                'time': elapsed,
                'text': resp.json().get('text', '') if resp.status_code == 200 else ''
            }

    def test_concurrent_recognition(self, audio_path, num_requests=10, max_workers=5):
        """并发识别性能测试"""
        print(f"\n1. 并发识别测试 ({num_requests}请求, {max_workers}并发)")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.test_single_recognition, audio_path)
                for _ in range(num_requests)
            ]

            start_time = time.time()
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
            total_time = time.time() - start_time

            success_results = [r for r in results if r['success']]
            times = [r['time'] for r in success_results]

            print(f"   总耗时: {total_time:.2f}秒")
            print(f"   成功: {len(success_results)}/{num_requests}")
            if times:
                print(f"   平均响应时间: {statistics.mean(times):.3f}秒")
                print(f"   中位数响应时间: {statistics.median(times):.3f}秒")
                print(f"   最小响应时间: {min(times):.3f}秒")
                print(f"   最大响应时间: {max(times):.3f}秒")
                print(f"   QPS: {len(success_results)/total_time:.2f}")

    def test_rtf(self, audio_path):
        """测试实时率(RTF = 处理时间/音频时长)"""
        print(f"\n2. 实时率测试")

        import soundfile as sf
        audio, sr = sf.read(audio_path)
        audio_duration = len(audio) / sr

        result = self.test_single_recognition(audio_path)

        if result['success']:
            rtf = result['time'] / audio_duration
            print(f"   音频时长: {audio_duration:.2f}秒")
            print(f"   处理时间: {result['time']:.2f}秒")
            print(f"   实时率(RTF): {rtf:.3f}")
            print(f"   实时倍数: {1/rtf:.1f}x")

    def test_memory_usage(self, audio_path, iterations=5):
        """测试内存使用情况（需要 psutil，可选）"""
        print(f"\n3. 连续处理测试 ({iterations}次)")

        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            base_memory = process.memory_info().rss / 1024 / 1024

            times = []
            for i in range(iterations):
                result = self.test_single_recognition(audio_path)
                times.append(result['time'])

                if i % 2 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    print(f"   第{i+1}次: 内存 {current_memory:.1f}MB, 时间 {result['time']:.2f}秒")

            final_memory = process.memory_info().rss / 1024 / 1024
            print(f"   初始内存: {base_memory:.1f}MB")
            print(f"   最终内存: {final_memory:.1f}MB")
            print(f"   内存增长: {final_memory - base_memory:.1f}MB")
            if times:
                print(f"   平均处理时间: {statistics.mean(times):.3f}秒")
        except ImportError:
            print("   (未安装 psutil，跳过内存监控)")
            times = []
            for i in range(iterations):
                result = self.test_single_recognition(audio_path)
                times.append(result['time'])
                print(f"   第{i+1}次: 耗时 {result['time']:.2f}秒")
            if times:
                print(f"   平均处理时间: {statistics.mean(times):.3f}秒")

    def run_all_tests(self, audio_path):
        """运行所有性能测试"""
        print("="*60)
        print("   FunASR 性能压力测试")
        print("="*60)

        if not Path(audio_path).exists():
            print(f"❌ 测试音频不存在: {audio_path}")
            return

        # 获取音频信息
        import soundfile as sf
        audio, sr = sf.read(audio_path)
        duration = len(audio) / sr
        size_kb = Path(audio_path).stat().st_size / 1024

        print(f"\n测试音频信息:")
        print(f"   文件: {Path(audio_path).name}")
        print(f"   时长: {duration:.2f}秒")
        print(f"   大小: {size_kb:.1f}KB")
        print(f"   采样率: {sr}Hz")

        # 运行各项测试
        self.test_rtf(audio_path)
        self.test_concurrent_recognition(audio_path, num_requests=10, max_workers=5)
        self.test_memory_usage(audio_path, iterations=5)

        print("\n" + "="*60)
        print("   性能测试完成")
        print("="*60)


if __name__ == "__main__":
    audio_file = sys.argv[1] if len(sys.argv) > 1 else "test_zh.wav"

    tester = PerformanceTest()
    tester.run_all_tests(audio_file)
