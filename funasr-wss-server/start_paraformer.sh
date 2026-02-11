#!/bin/bash

# FunASR Paraformer-zh 服务器启动脚本

# 切换到脚本所在目录，确保相对路径正确
cd "$(dirname "$0")"

echo "========================================="
echo "  FunASR Paraformer-zh 服务器启动脚本"
echo "========================================="
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到python3"
    exit 1
fi

# 安装依赖
echo "📦 安装依赖..."
pip3 install -r ./requirements.txt -q

# 检查模型
# echo "🔄 检查并下载模型..."
# python3 -c "
# from funasr import AutoModel
# print('下载 paraformer-zh 模型...')
# model = AutoModel(model='paraformer-zh', disable_update=True)
# print('下载 fsmn-vad 模型...')
# model = AutoModel(model='fsmn-vad', disable_update=True)
# print('下载 ct-punc 模型...')
# model = AutoModel(model='ct-punc', disable_update=True)
# print('✅ 模型准备完成')
# " 2>/dev/null || {
#     echo "❌ 模型下载失败"
#     exit 1
# }

# 启动服务器
echo ""
echo "🚀 启动服务器..."
echo "模型: paraformer-zh (离线高精度识别)"
echo "端口: 10095"
echo ""

python3 ./app_paraformer.py
