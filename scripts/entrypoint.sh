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

echo ""
echo "=========================================="
echo "启动 OpenClaw Gateway"
echo "=========================================="
echo ""

# 启动应用（执行传入的命令）
exec "$@"
