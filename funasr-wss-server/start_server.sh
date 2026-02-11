#!/bin/bash

# FunASR WebSocket 服务器启动脚本

# 设置Python环境（如果有虚拟环境）
# source venv/bin/activate

# 安装依赖
pip install -r requirements.txt -q

# 下载模型（第一次运行）
echo "正在下载模型..."
python -c "from funasr import AutoModel; model = AutoModel(model='paraformer-zh-streaming')"

# 启动服务器
echo "启动 FunASR WebSocket 服务器..."
python app.py
