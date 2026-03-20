# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV HOME=/root
ENV MODELSCOPE_CACHE=/root/.cache/modelscope
ENV HF_HOME=/root/.cache/huggingface
# 模型选择（auth-choice方式）
ENV AUTH_CHOICE=""
ENV KEY_NAME=""
ENV API_KEY=""
ENV MODEL_NAME=""

# 模型选择（非auth-choice方式,需要保证API_KEY、MODEL_TYPE有值） anthropic、opencode
ENV MODEL_TYPE=""

# 自定义模型
ENV CUSTOM_MODEL_BASE_PATH=""
ENV CUSTOM_MODEL_API_KEY=""
ENV CUSTOM_MODEL_NAME=""
# 模型提供者
ENV CUSTOM_MODEL_PROVIDER=""

# 设置openclaw版本（运行时传入，默认 latest）
ENV OPENCLAW_VERSION="latest"

# 设置联网搜索
ENV SEARCH_PROVIDER=""
ENV SEARCH_API_KEY=""
ENV SEARCH_BASE_URL=""

WORKDIR /root

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

# 升级 pip，安装 PyTorch 和 torchaudio (CPU)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install \
        "torch>=1.13" \
        torchaudio \
        --index-url https://download.pytorch.org/whl/cpu

# 安装 funasr 及依赖
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -U funasr modelscope huggingface

# 仅先复制 requirements.txt，代码变动时不触发重新安装
COPY ./funasr-wss-server/requirements.txt /root/funasr-wss-server/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /root/funasr-wss-server/requirements.txt

# 复制 funasr-wss-server 完整代码
COPY ./funasr-wss-server /root/funasr-wss-server

# 复制 package.json 并安装根依赖
COPY ./package.json /root/package.json
RUN --mount=type=cache,target=/root/.npm \
    npm install --prefer-offline

# 仅先复制插件 package.json，插件代码变动时不触发重新安装
COPY ./plugins/openclaw-plugin-askaway/actor-rtc-actr-0.1.14.tgz /root/plugins/openclaw-plugin-askaway/actor-rtc-actr-0.1.14.tgz
COPY ./plugins/openclaw-plugin-askaway/package.json /root/plugins/openclaw-plugin-askaway/package.json
RUN --mount=type=cache,target=/root/.npm \
    cd /root/plugins/openclaw-plugin-askaway && npm install --prefer-offline

# 复制其余文件（变动最频繁，放最后以充分利用缓存）
COPY ./model-cache /root/.cache
COPY ./assets /root/assets
COPY ./plugins /root/plugins
COPY ./scripts /root/scripts
RUN chmod +x /root/scripts/entrypoint.sh

# 暴露端口（根据 openclaw.json 中的配置）
EXPOSE 18789

# 设置启动脚本为 ENTRYPOINT
ENTRYPOINT ["/root/scripts/entrypoint.sh"]

# 启动命令
CMD ["openclaw", "gateway", "run"]