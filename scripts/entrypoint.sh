#!/bin/bash
set -e

echo "=========================================="
echo "OpenClaw 容器启动脚本"
echo "=========================================="

# 动态安装 openclaw
echo "安装 OpenClaw..."
if [ -z "$OPENCLAW_VERSION" ] || [ "$OPENCLAW_VERSION" = "latest" ]; then
  echo "  版本: latest"
  npm install -g openclaw
else
  echo "  版本: $OPENCLAW_VERSION"
  npm install -g openclaw@${OPENCLAW_VERSION}
fi
echo "✓ OpenClaw 安装成功: $(openclaw --version 2>/dev/null || echo '未知')"
echo ""

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

# 判断是否使用自定义模型模式
USE_CUSTOM_MODEL=false
if [ -n "$CUSTOM_MODEL_BASE_PATH" ] && [ -n "$CUSTOM_MODEL_API_KEY" ] && [ -n "$CUSTOM_MODEL_NAME" ] && [ -n "$CUSTOM_MODEL_PROVIDER" ]; then
  USE_CUSTOM_MODEL=true
fi

if [ "$USE_CUSTOM_MODEL" = "true" ]; then
  # 自定义模型模式：使用 skip auth 执行 onboard，然后修改 openclaw.json
  echo "检测到自定义模型配置，使用自定义模型模式..."
  echo "执行 openclaw onboard (skip auth)..."
  if openclaw onboard \
    --non-interactive \
    --accept-risk \
    --auth-choice skip \
    --skip-daemon \
    --skip-skills \
    --skip-health; then
    echo "✓ openclaw onboard 成功"
  else
    echo "✗ openclaw onboard 失败"
    exit 1
  fi
  echo ""

  echo "修改 openclaw.json 自定义模型配置..."
  if node /root/scripts/modify-custom-model.js; then
    echo "✓ openclaw.json 更新成功"
  else
    echo "✗ openclaw.json 更新失败"
    exit 1
  fi
  echo ""
else
  # 执行 openclaw onboard（支持 AUTH_CHOICE 或 MODEL_TYPE 方式）
  SHOULD_RUN_ONBOARD=false
  ONBOARD_ARGS=(--non-interactive --accept-risk --skip-health)

  if [ -n "$AUTH_CHOICE" ]; then
    SHOULD_RUN_ONBOARD=true
    ONBOARD_ARGS+=(--auth-choice "$AUTH_CHOICE")
    if [ -n "$KEY_NAME" ] && [ -n "$API_KEY" ]; then
      ONBOARD_ARGS+=("--$KEY_NAME" "$API_KEY")
    fi
  elif [ -n "$MODEL_TYPE" ] && [ -n "$API_KEY" ]; then
    case "$MODEL_TYPE" in
      anthropic)
        SHOULD_RUN_ONBOARD=true
        ONBOARD_ARGS+=(--anthropic-api-key "$API_KEY")
        ;;
      opencode)
        SHOULD_RUN_ONBOARD=true
        ONBOARD_ARGS+=(--opencode-zen-api-key "$API_KEY")
        ;;
      *)
        echo "⚠️  未支持的 MODEL_TYPE: $MODEL_TYPE，跳过 openclaw onboard"
        ;;
    esac
  fi

  if [ "$SHOULD_RUN_ONBOARD" = "true" ]; then
    echo "执行 openclaw onboard 命令: openclaw onboard ${ONBOARD_ARGS[@]}"
    if openclaw onboard "${ONBOARD_ARGS[@]}"; then
      echo "✓ openclaw onboard 成功"
    else
      echo "✗ openclaw onboard 失败"
      exit 1
    fi
    echo ""
  fi
fi

# echo "启动 FunASR Paraformer-zh 服务器..."
# # 在后台启动 FunASR 服务器
# /root/funasr-wss-server/start_paraformer.sh > /tmp/funasr.log 2>&1 &
# FUNASR_PID=$!
# echo "FunASR Paraformer-zh 服务器已在后台启动 (PID: $FUNASR_PID)"
# echo "等待服务器初始化..."

# # 检查服务是否启动成功（最多等待30秒）
# FUNASR_PORT=10095
# MAX_WAIT=180
# WAIT_COUNT=0
# while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
#     # 检查进程是否还在运行
#     if ! kill -0 $FUNASR_PID 2>/dev/null; then
#         echo "❌ FunASR 服务器进程已退出，启动失败"
#         echo "查看日志:"
#         tail -20 /tmp/funasr.log
#         exit 1
#     fi
    
#     # 检查端口是否在监听
#     # 方法1: 使用 /proc/net/tcp (Linux 系统，无需额外工具)
#     PORT_HEX=$(printf "%04X" $FUNASR_PORT)
#     if [ -f /proc/net/tcp ] && grep -q ":$PORT_HEX " /proc/net/tcp 2>/dev/null; then
#         echo "✓ FunASR 服务器启动成功，端口 $FUNASR_PORT 已监听"
#         break
#     # 方法2: 使用 nc (如果可用)
#     elif command -v nc >/dev/null 2>&1; then
#         if nc -z localhost $FUNASR_PORT 2>/dev/null; then
#             echo "✓ FunASR 服务器启动成功，端口 $FUNASR_PORT 已监听"
#             break
#         fi
#     # 方法3: 使用 ss (如果可用)
#     elif command -v ss >/dev/null 2>&1; then
#         if ss -ln | grep -q ":$FUNASR_PORT "; then
#             echo "✓ FunASR 服务器启动成功，端口 $FUNASR_PORT 已监听"
#             break
#         fi
#     # 方法4: 使用 Python 检查端口 (Python 已安装)
#     elif command -v python3 >/dev/null 2>&1; then
#         if python3 -c "import socket; s=socket.socket(); s.settimeout(1); result=s.connect_ex(('localhost', $FUNASR_PORT)); s.close(); exit(0 if result == 0 else 1)" 2>/dev/null; then
#             echo "✓ FunASR 服务器启动成功，端口 $FUNASR_PORT 已监听"
#             break
#         fi
#     fi
    
#     sleep 1
#     WAIT_COUNT=$((WAIT_COUNT + 1))
# done

# if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
#     echo "⚠️  警告: 等待超时，无法确认 FunASR 服务器是否完全启动"
#     echo "进程状态: $(kill -0 $FUNASR_PID 2>/dev/null && echo '运行中' || echo '已退出')"
#     echo "查看日志: tail -20 /tmp/funasr.log"
# fi
echo ""

# echo ""
echo "=========================================="
echo "启动 OpenClaw Gateway"
echo "=========================================="
echo ""

# 设置模型
if [ "$USE_CUSTOM_MODEL" = "true" ]; then
  echo "设置自定义模型: $CUSTOM_MODEL_PROVIDER/$CUSTOM_MODEL_NAME"
  openclaw models set "$CUSTOM_MODEL_PROVIDER/$CUSTOM_MODEL_NAME"
  echo "✓ 模型已设置为: $CUSTOM_MODEL_PROVIDER/$CUSTOM_MODEL_NAME"
elif [ -n "$MODEL_NAME" ]; then
  # 如果 MODEL_NAME 有值，则设置模型
  echo "设置模型: $MODEL_NAME"
  openclaw models set "$MODEL_NAME"
  echo "✓ 模型已设置为: $MODEL_NAME"
fi

# 启动应用（执行传入的命令）
exec "$@"
