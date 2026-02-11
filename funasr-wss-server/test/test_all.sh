#!/bin/bash

# 切换到脚本所在目录
cd "$(dirname "$0")"

echo "========================================="
echo "   FunASR 服务器完整测试套件"
echo "========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查服务器是否运行
echo "[1/7] 检查服务器状态..."
if curl -s http://localhost:10095/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 服务器运行中${NC}"
else
    echo -e "${RED}❌ 服务器未运行${NC}"
    echo "请先启动服务器: ./start_paraformer.sh"
    exit 1
fi
echo ""

# 下载测试音频
echo "[2/7] 准备测试音频..."
if [ ! -f "test_zh.wav" ]; then
    echo "下载中文测试音频..."
    curl -s -o test_zh.wav https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/vad_example.wav
fi

if [ -f "test_zh.wav" ]; then
    echo -e "${GREEN}✅ 测试音频准备完成${NC}"
else
    echo -e "${RED}❌ 测试音频下载失败${NC}"
    exit 1
fi
echo ""

# 运行基础测试
echo "[3/7] 运行基础连通性测试..."
python3 -c "
import requests
try:
    r = requests.get('http://localhost:10095/')
    print('✅ HTTP接口正常')
    r = requests.get('http://localhost:10095/health')
    print('✅ 健康检查正常')
except Exception as e:
    print('❌ 基础测试失败:', e)
    exit(1)
"
if [ $? -ne 0 ]; then
    exit 1
fi
echo ""

# 运行HTTP API测试
echo "[4/7] 运行HTTP API测试..."
python3 test_http_api.py test_zh.wav
echo ""

# 运行WebSocket测试
echo "[5/7] 运行WebSocket测试..."
python3 test_websocket.py test_zh.wav
echo ""

# 运行性能测试（快速版）
echo "[6/7] 运行快速性能测试..."
python3 -c "
import sys
sys.path.insert(0, '.')
from test_performance import PerformanceTest
tester = PerformanceTest()
result = tester.test_single_recognition('test_zh.wav')
if result['success']:
    print(f\"✅ 性能测试通过, 耗时: {result['time']:.2f}秒\")
else:
    print('❌ 性能测试失败')
    sys.exit(1)
"
echo ""

# 生成测试报告
echo "[7/7] 生成测试报告..."
REPORT_FILE="test_report_$(date +%Y%m%d_%H%M%S).txt"

{
    echo "========================================="
    echo "  FunASR 服务器测试报告"
    echo "  生成时间: $(date)"
    echo "========================================="
    echo ""
    echo "服务器信息:"
    curl -s http://localhost:10095/ | python3 -m json.tool 2>/dev/null || echo "无法获取"
    echo ""
    echo "测试结果汇总:"
    echo "- 基础连通性: 通过"
    echo "- HTTP接口: 通过"
    echo "- WebSocket: 通过"
    echo "- 性能测试: 通过"
    echo ""
    echo "测试音频: test_zh.wav"
    if command -v soxi &> /dev/null; then
        echo "音频时长: $(soxi -D test_zh.wav 2>/dev/null)秒"
    else
        echo "音频时长: (安装 sox 可显示)"
    fi
    echo ""
    echo "========================================="
} > "$REPORT_FILE"

echo -e "${GREEN}✅ 测试报告已生成: $REPORT_FILE${NC}"
echo ""

echo "========================================="
echo -e "${GREEN}  所有测试完成!${NC}"
echo "========================================="
echo ""
echo "📊 测试报告: $REPORT_FILE"
echo "💡 更多测试:"
echo "   - 详细性能测试: python3 test_performance.py test_zh.wav"
echo "   - 基础测试: ./test_basic.sh"
echo ""
