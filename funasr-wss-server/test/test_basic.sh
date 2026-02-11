#!/bin/bash

echo "========================================="
echo "  FunASR Paraformer 服务器基础测试"
echo "========================================="
echo ""

# 测试1: 健康检查
echo "[测试1] 健康检查..."
curl -s http://localhost:10095/health | python3 -m json.tool
if [ $? -eq 0 ]; then
    echo "✅ 健康检查通过"
else
    echo "❌ 健康检查失败 - 服务器可能未启动"
    exit 1
fi
echo ""

# 测试2: 服务器信息
echo "[测试2] 获取服务器信息..."
curl -s http://localhost:10095/ | python3 -m json.tool
echo ""

# 测试3: 下载测试音频（如果没有）
echo "[测试3] 准备测试音频..."
TEST_AUDIO="test_zh.wav"
if [ ! -f "$TEST_AUDIO" ]; then
    echo "下载测试音频文件..."
    curl -o $TEST_AUDIO https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/vad_example.wav
    echo "✅ 测试音频下载完成: $TEST_AUDIO"
else
    echo "✅ 测试音频已存在: $TEST_AUDIO"
fi
echo ""

# 测试4: HTTP文件上传识别
echo "[测试4] HTTP文件上传识别测试..."
curl -s -X POST http://localhost:10095/api/asr/file \
  -F "file=@$TEST_AUDIO" \
  -F "hotword=阿里巴巴 达摩院" | python3 -m json.tool
echo ""

# 测试5: WebSocket简单测试（使用websocat）
echo "[测试5] WebSocket连接测试..."
if command -v websocat &> /dev/null; then
    echo "测试WebSocket连接..."
    echo '{"action":"end"}' | websocat ws://localhost:10095/ws/asr -1 -t 2>/dev/null && echo "✅ WebSocket连接正常" || echo "⚠️ WebSocket连接异常（可能已连接但协议不匹配）"
else
    echo "⚠️ 未安装websocat，跳过WebSocket测试"
    echo "安装: brew install websocat  (Mac)"
    echo "      apt install websocat  (Linux)"
fi

echo ""
echo "========================================="
echo "✅ 基础测试完成"
echo "========================================="
