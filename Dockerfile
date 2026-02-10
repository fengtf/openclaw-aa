FROM python:3.11-slim

ENV HOME=/root
ENV MODELSCOPE_CACHE=/root/.cache/modelscope
ENV HF_HOME=/root/.cache/huggingface

# 安装系统依赖和 Node.js 24
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    gnupg \
    ffmpeg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_24.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 升级 pip
RUN pip install --upgrade pip

# 安装 PyTorch 和 torchaudio (CPU)
RUN pip install --no-cache-dir \
    torch>=1.13 \
    torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

# 安装 funasr 及依赖
RUN pip install --no-cache-dir -U \
    funasr \
    modelscope \
    huggingface

# 下载模型到镜像缓存（离线可用）
# RUN python3 -c "from funasr import AutoModel; AutoModel(model='FunAudioLLM/Fun-ASR-Nano-2512')" && \
#     python3 -c "from funasr import AutoModel; AutoModel(model='fsmn-vad')" && \
#     python3 -c "from funasr import AutoModel; AutoModel(model='ct-punc')"

# 设置工作目录
WORKDIR /root

# 全局安装 openclaw
RUN npm install -g openclaw

# 创建 .openclaw 目录
RUN mkdir -p /root/.openclaw

# 复制 package.json
COPY ./package.json /root/package.json
RUN cd /root && npm install

# 将本地 openclaw 目录的所有内容复制到镜像的 /root/.openclaw 中
COPY ./openclaw /root/.openclaw

COPY ./model-cache /root/.cache
COPY ./assets /root/assets


# 安装插件依赖
RUN cd /root/.openclaw/plugins/openclaw-plugin-askaway && npm install

# 复制启动脚本
COPY ./scripts /root/scripts
RUN chmod +x /root/scripts/entrypoint.sh

# 暴露端口（根据 openclaw.json 中的配置）
EXPOSE 18789

# 设置启动脚本为 ENTRYPOINT
ENTRYPOINT ["/root/scripts/entrypoint.sh"]

# 启动命令
CMD ["openclaw", "gateway", "run"]