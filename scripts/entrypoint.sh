#!/bin/bash
set -e

echo "=========================================="
echo "OpenClaw 容器启动脚本"
echo "=========================================="

# 验证所有必需的环境变量是否已设置
echo "检查环境变量..."
MISSING_VARS=()

for var in RTC_REALM_ID RTC_SIGNALING_SERVER RTC_TURN_SERVER RTC_STUN_SERVER; do
  if [ -z "${!var}" ]; then
    MISSING_VARS+=("$var")
  fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
  echo "错误: 以下环境变量未设置:"
  for var in "${MISSING_VARS[@]}"; do
    echo "  - $var"
  done
  echo ""
  echo "请使用 -e 参数传入所有必需的环境变量，例如:"
  echo "  docker run -e RTC_REALM_ID=xxx -e RTC_SIGNALING_SERVER=xxx ..."
  exit 1
fi

echo "✓ 所有环境变量已设置"
echo ""

# 显示配置信息
echo "配置信息:"
echo "  RTC_REALM_ID: $RTC_REALM_ID"
echo "  RTC_SIGNALING_SERVER: $RTC_SIGNALING_SERVER"
echo "  RTC_TURN_SERVER: $RTC_TURN_SERVER"
echo "  RTC_STUN_SERVER: $RTC_STUN_SERVER"
echo ""

# 执行配置修改脚本
echo "修改配置文件..."
if node /root/scripts/modify-config.js; then
  echo "✓ 配置文件修改成功"
else
  echo "✗ 配置文件修改失败"
  exit 1
fi

echo "启动 FunASR Paraformer-zh 服务器..."
# 在后台启动 FunASR 服务器
/root/funasr-wss-server/start_paraformer.sh > /tmp/funasr.log 2>&1 &
FUNASR_PID=$!
echo "FunASR Paraformer-zh 服务器已在后台启动 (PID: $FUNASR_PID)"
echo "等待服务器初始化..."

# 检查服务是否启动成功（最多等待30秒）
FUNASR_PORT=10095
MAX_WAIT=180
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    # 检查进程是否还在运行
    if ! kill -0 $FUNASR_PID 2>/dev/null; then
        echo "❌ FunASR 服务器进程已退出，启动失败"
        echo "查看日志:"
        tail -20 /tmp/funasr.log
        exit 1
    fi
    
    # 检查端口是否在监听
    # 方法1: 使用 /proc/net/tcp (Linux 系统，无需额外工具)
    PORT_HEX=$(printf "%04X" $FUNASR_PORT)
    if [ -f /proc/net/tcp ] && grep -q ":$PORT_HEX " /proc/net/tcp 2>/dev/null; then
        echo "✓ FunASR 服务器启动成功，端口 $FUNASR_PORT 已监听"
        break
    # 方法2: 使用 nc (如果可用)
    elif command -v nc >/dev/null 2>&1; then
        if nc -z localhost $FUNASR_PORT 2>/dev/null; then
            echo "✓ FunASR 服务器启动成功，端口 $FUNASR_PORT 已监听"
            break
        fi
    # 方法3: 使用 ss (如果可用)
    elif command -v ss >/dev/null 2>&1; then
        if ss -ln | grep -q ":$FUNASR_PORT "; then
            echo "✓ FunASR 服务器启动成功，端口 $FUNASR_PORT 已监听"
            break
        fi
    # 方法4: 使用 Python 检查端口 (Python 已安装)
    elif command -v python3 >/dev/null 2>&1; then
        if python3 -c "import socket; s=socket.socket(); s.settimeout(1); result=s.connect_ex(('localhost', $FUNASR_PORT)); s.close(); exit(0 if result == 0 else 1)" 2>/dev/null; then
            echo "✓ FunASR 服务器启动成功，端口 $FUNASR_PORT 已监听"
            break
        fi
    fi
    
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo "⚠️  警告: 等待超时，无法确认 FunASR 服务器是否完全启动"
    echo "进程状态: $(kill -0 $FUNASR_PID 2>/dev/null && echo '运行中' || echo '已退出')"
    echo "查看日志: tail -20 /tmp/funasr.log"
fi
echo ""

echo ""
echo "=========================================="
echo "启动 OpenClaw Gateway"
echo "=========================================="
echo ""

# 启动应用（执行传入的命令）
exec "$@"
