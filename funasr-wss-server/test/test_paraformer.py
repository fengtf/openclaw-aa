#!/usr/bin/env python3
"""测试 Paraformer-zh 服务器"""

import requests
import json
import time

def test_server_health():
    """测试服务器健康状态"""
    try:
        response = requests.get("http://localhost:10095/health")
        print(f"健康检查: {response.json()}")
        return True
    except Exception as e:
        print(f"服务器未启动: {e}")
        return False

def test_server_info():
    """测试服务器信息"""
    try:
        response = requests.get("http://localhost:10095/")
        info = response.json()
        print("\n服务器信息:")
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return True
    except Exception as e:
        print(f"获取服务器信息失败: {e}")
        return False

if __name__ == "__main__":
    print("测试 FunASR Paraformer-zh 服务器...")
    
    if test_server_health():
        test_server_info()
        print("\n✅ 服务器运行正常")
        print("\nWebSocket端点: ws://localhost:10095/ws/asr")
        print("HTTP端点: http://localhost:10095")
        print("\n客户端使用示例:")
        print("  python client_paraformer.py test.wav")
        print("  python client_paraformer.py test.wav --hotword '阿里巴巴 达摩院'")
        print("  python client_paraformer.py test.wav --mode http")
    else:
        print("\n❌ 请先启动服务器: python app_paraformer.py")
