import asyncio
import json
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 延迟导入，便于在无 GPU 环境下先启动再加载模型
def _load_funasr():
    from funasr import AutoModel
    return AutoModel


class ASRWebSocketServer:
    def __init__(self, config_path: str = "config.yaml"):
        """初始化ASR服务器"""
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 初始化模型
        self.model = self._load_model()
        
        # 连接管理
        self.active_connections: Dict[str, Dict] = {}
        
        # 服务器配置
        self.host = self.config['server']['host']
        self.port = self.config['server']['port']
        self.chunk_duration_ms = self.config['server']['chunk_duration_ms']
        self.sample_rate = self.config['server']['sample_rate']
        
        # 计算每个chunk的采样点数
        self.chunk_samples = int(self.sample_rate * self.chunk_duration_ms / 1000)
        
        logger.info(f"ASR服务器初始化完成，使用模型: {self.config['models']['asr_model']}")
    
    def _load_model(self):
        """加载ASR模型"""
        model_config = self.config['models']
        AutoModel = _load_funasr()
        
        try:
            model = AutoModel(
                model=model_config['asr_model'],
                vad_model=model_config.get('vad_model'),
                punc_model=model_config.get('punc_model'),
                device=model_config.get('device', 'cpu'),
                hub=model_config.get('model_hub', 'ms'),
                disable_update=True
            )
            logger.info("模型加载成功")
            return model
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise
    
    async def handle_websocket_connection(self, websocket: WebSocket, client_id: str):
        """处理WebSocket连接"""
        await websocket.accept()
        
        # 初始化客户端状态
        self.active_connections[client_id] = {
            'websocket': websocket,
            'cache': {},
            'audio_buffer': np.array([], dtype=np.float32),
            'is_final': False,
            'session_start': datetime.now(),
            'chunks_processed': 0
        }
        
        logger.info(f"客户端 {client_id} 已连接")
        
        try:
            while True:
                # 同时支持二进制音频和文本控制消息
                message = await websocket.receive()
                if "bytes" in message and message["bytes"]:
                    await self.process_audio_chunk(client_id, message["bytes"])
                elif "text" in message and message["text"]:
                    try:
                        data = json.loads(message["text"])
                        if data.get("action") == "end":
                            # 处理剩余缓冲区并发送最终结果
                            if client_id in self.active_connections:
                                await self._flush_audio_buffer(client_id)
                            break
                    except json.JSONDecodeError:
                        pass
        except WebSocketDisconnect:
            logger.info(f"客户端 {client_id} 断开连接")
        
        except Exception as e:
            logger.error(f"处理客户端 {client_id} 时出错: {e}")
        
        finally:
            if client_id in self.active_connections:
                del self.active_connections[client_id]
    
    async def _flush_audio_buffer(self, client_id: str):
        """将缓冲区剩余音频处理完毕"""
        client_info = self.active_connections.get(client_id)
        if not client_info or len(client_info['audio_buffer']) == 0:
            return
        # 用零填充到 chunk 长度
        buf = client_info['audio_buffer']
        pad = self.chunk_samples - (len(buf) % self.chunk_samples)
        if pad < self.chunk_samples:
            buf = np.concatenate([buf, np.zeros(pad, dtype=np.float32)])
        for i in range(0, len(buf), self.chunk_samples):
            chunk = buf[i:i + self.chunk_samples]
            is_final = (i + self.chunk_samples) >= len(buf)
            await self._run_asr_chunk(client_id, chunk, is_final)
        client_info['audio_buffer'] = np.array([], dtype=np.float32)
    
    async def _run_asr_chunk(self, client_id: str, chunk: np.ndarray, is_final: bool):
        """执行单次 ASR 推理并发送结果"""
        client_info = self.active_connections.get(client_id)
        if not client_info:
            return
        try:
            result = self.model.generate(
                input=chunk,
                cache=client_info['cache'],
                is_final=is_final,
                chunk_size=self.config['chunk_config']['chunk_size'],
                encoder_chunk_look_back=self.config['chunk_config']['encoder_chunk_look_back'],
                decoder_chunk_look_back=self.config['chunk_config']['decoder_chunk_look_back']
            )
            if result and len(result) > 0:
                text = result[0].get('text', '')
                if text:
                    response = {
                        'text': text,
                        'is_final': is_final,
                        'timestamp': datetime.now().isoformat(),
                        'chunk_id': client_info['chunks_processed']
                    }
                    await client_info['websocket'].send_text(json.dumps(response, ensure_ascii=False))
            client_info['chunks_processed'] += 1
        except Exception as e:
            logger.error(f"ASR 推理出错: {e}")
            await client_info['websocket'].send_text(json.dumps({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }, ensure_ascii=False))
    
    async def process_audio_chunk(self, client_id: str, audio_data: bytes):
        """处理音频chunk"""
        client_info = self.active_connections.get(client_id)
        if not client_info:
            return
        
        try:
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            client_info['audio_buffer'] = np.concatenate([
                client_info['audio_buffer'],
                audio_array
            ])
            
            while len(client_info['audio_buffer']) >= self.chunk_samples:
                chunk = client_info['audio_buffer'][:self.chunk_samples].copy()
                client_info['audio_buffer'] = client_info['audio_buffer'][self.chunk_samples:]
                is_final = len(client_info['audio_buffer']) == 0
                await self._run_asr_chunk(client_id, chunk, is_final)
        
        except Exception as e:
            logger.error(f"处理音频chunk时出错: {e}")
            error_response = {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            await client_info['websocket'].send_text(json.dumps(error_response, ensure_ascii=False))


class ASRRequest(BaseModel):
    """ASR请求模型"""
    audio_path: Optional[str] = None
    audio_data: Optional[str] = None  # base64编码的音频数据
    sample_rate: int = 16000
    language: str = "zh"


# 创建FastAPI应用
app = FastAPI(title="FunASR WebSocket Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

server = None


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化服务器"""
    global server
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        default_config = {
            'server': {
                'host': '0.0.0.0',
                'port': 10095,
                'max_connections': 100,
                'chunk_duration_ms': 600,
                'sample_rate': 16000
            },
            'models': {
                'asr_model': 'paraformer-zh',
                'vad_model': 'fsmn-vad',
                'punc_model': 'ct-punc',
                'device': 'cpu'
            },
            'chunk_config': {
                'chunk_size': [0, 10, 5],
                'encoder_chunk_look_back': 4,
                'decoder_chunk_look_back': 1
            }
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
    
    server = ASRWebSocketServer(str(config_path))


@app.get("/")
async def root():
    """根路径，返回服务器状态"""
    return {
        "status": "running",
        "service": "FunASR WebSocket Server",
        "model": server.config['models']['asr_model'] if server else None,
        "connections": len(server.active_connections) if server else 0
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


@app.websocket("/ws/asr")
async def websocket_asr(websocket: WebSocket):
    """ASR WebSocket端点"""
    client_id = f"{websocket.client.host}:{websocket.client.port}"
    
    if server:
        await server.handle_websocket_connection(websocket, client_id)
    else:
        await websocket.close(code=1008, reason="Server not initialized")


@app.post("/api/asr")
async def offline_asr(request: ASRRequest):
    """离线ASR端点（用于文件转写）"""
    if not server:
        return {"error": "Server not initialized"}
    
    try:
        return {
            "text": "离线ASR功能待实现",
            "status": "success"
        }
    except Exception as e:
        logger.error(f"离线ASR处理失败: {e}")
        return {"error": str(e), "status": "failed"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=10095,
        log_level="info"
    )
