import json
import logging
import yaml
import base64
from pathlib import Path
from typing import Dict
from datetime import datetime
import tempfile

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import soundfile as sf

from funasr import AutoModel

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ParaformerServer:
    """使用 paraformer-zh 的 ASR 服务器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """初始化服务器"""
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
        self.sample_rate = self.config['server']['sample_rate']
        
        # ASR配置
        self.batch_size_s = self.config['asr_config']['batch_size_s']
        self.hotword = self.config['asr_config'].get('hotword')
        
        logger.info(f"Paraformer服务器初始化完成，使用模型: {self.config['models']['asr_model']}")
        logger.info(f"设备: {self.config['models']['device']}")
    
    def _load_model(self) -> AutoModel:
        """加载 paraformer-zh 模型和相关组件"""
        model_config = self.config['models']
        
        try:
            # 移除 log_level 参数，或者在传入前确保是字符串
            model_kwargs = {
                'model': model_config['asr_model'],
                'vad_model': model_config.get('vad_model'),
                'punc_model': model_config.get('punc_model'),
                'spk_model': model_config.get('spk_model'),
                'device': model_config.get('device', 'cpu'),
                'hub': model_config.get('model_hub', 'ms'),
                'disable_update': True,
                # 不使用 log_level 参数，或者使用字符串
            }
            
            # 如果确实需要设置日志级别，可以这样处理
            if 'log_level' in model_config:
                log_level_str = model_config['log_level']
                if isinstance(log_level_str, int):
                    # 如果是整数，转换为对应的字符串
                    level_map = {
                        0: 'NOTSET',
                        10: 'DEBUG',
                        20: 'INFO',
                        30: 'WARNING',
                        40: 'ERROR',
                        50: 'CRITICAL'
                    }
                    model_kwargs['log_level'] = level_map.get(log_level_str, 'INFO')
                else:
                    model_kwargs['log_level'] = str(log_level_str)
            
            model = AutoModel(**model_kwargs)
            
            logger.info("✓ Paraformer-zh 模型加载成功")
            if model_config.get('vad_model'):
                logger.info(f"✓ VAD模型加载成功: {model_config['vad_model']}")
            if model_config.get('punc_model'):
                logger.info(f"✓ 标点模型加载成功: {model_config['punc_model']}")
            
            return model
            
        except Exception as e:
            logger.error(f"✗ 模型加载失败: {e}")
            logger.error(f"模型配置: {model_config}")
            raise
    
    async def process_audio_file(self, audio_path: str, client_id: str = None) -> Dict:
        """处理完整的音频文件"""
        try:
            logger.info(f"开始处理音频: {audio_path}")
            
            # 构建推理参数
            kwargs = {
                "input": audio_path,
                "batch_size_s": self.batch_size_s,
                "cache": {}
            }
            
            # 添加热词（如果配置了）
            if self.hotword:
                kwargs["hotword"] = self.hotword
            
            # 执行ASR推理
            results = self.model.generate(**kwargs)
            
            if results and len(results) > 0:
                result = results[0]
                
                # 构建完整响应
                response = {
                    "success": True,
                    "text": result.get("text", ""),
                    "timestamp": datetime.now().isoformat(),
                    "client_id": client_id,
                    "detail": {
                        "sentences": result.get("sentences", []),  # 句子级别结果
                        "spk_info": result.get("spk", []),        # 说话人信息
                    }
                }
                
                # 计算处理时间
                logger.info(f"✓ 音频处理完成，识别文本: {result.get('text', '')[:100]}...")
                return response
            else:
                return {
                    "success": False,
                    "error": "未能识别出任何内容",
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"处理音频文件失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def handle_websocket_connection(self, websocket: WebSocket, client_id: str):
        """
        处理WebSocket连接
        对于paraformer-zh模型，我们采用完整的音频文件接收模式
        """
        await websocket.accept()
        
        # 初始化客户端状态
        temp_dir = Path(tempfile.gettempdir()) / "funasr_audio"
        temp_dir.mkdir(exist_ok=True)
        
        client_info = {
            'websocket': websocket,
            'audio_chunks': [],  # 存储音频chunk
            'session_start': datetime.now(),
            'temp_dir': temp_dir,
            'total_bytes': 0
        }
        
        self.active_connections[client_id] = client_info
        logger.info(f"客户端 {client_id} 已连接")
        
        try:
            # 发送欢迎消息
            await websocket.send_text(json.dumps({
                "type": "connected",
                "message": "Paraformer-zh ASR 服务器已连接",
                "mode": "离线识别模式（接收完整音频后处理）",
                "timestamp": datetime.now().isoformat()
            }, ensure_ascii=False))
            
            while True:
                # 接收消息 (FastAPI WebSocket 返回 dict: {"text": "..."} 或 {"bytes": b"..."})
                message = await websocket.receive()
                
                # 处理二进制音频数据
                if "bytes" in message and message["bytes"]:
                    client_info['audio_chunks'].append(message["bytes"])
                    client_info['total_bytes'] += len(message["bytes"])
                    
                    # 每接收100KB反馈一次
                    if client_info['total_bytes'] // 102400 > len(client_info['audio_chunks']) // 10:
                        await websocket.send_text(json.dumps({
                            "type": "progress",
                            "message": f"已接收 {client_info['total_bytes'] / 1024:.1f}KB 音频数据",
                            "timestamp": datetime.now().isoformat()
                        }, ensure_ascii=False))
                
                # 处理文本消息（控制命令）
                elif "text" in message and message["text"]:
                    cmd = json.loads(message["text"])
                    
                    if cmd.get('action') == 'end':
                        # 结束接收，开始识别
                        break
                    
                    elif cmd.get('action') == 'cancel':
                        # 取消识别
                        client_info['audio_chunks'] = []
                        await websocket.send_text(json.dumps({
                            "type": "cancelled",
                            "message": "已取消识别",
                            "timestamp": datetime.now().isoformat()
                        }, ensure_ascii=False))
                        return
            
            # 开始识别完整的音频
            if client_info['audio_chunks']:
                await self._recognize_audio(client_id)
            
        except WebSocketDisconnect:
            logger.info(f"客户端 {client_id} 断开连接")
        
        except Exception as e:
            logger.error(f"处理客户端 {client_id} 时出错: {e}")
            try:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }, ensure_ascii=False))
            except Exception:
                pass
        
        finally:
            # 清理临时文件
            self._cleanup_client(client_id)
    
    async def _recognize_audio(self, client_id: str):
        """识别完整的音频数据"""
        client_info = self.active_connections.get(client_id)
        if not client_info or not client_info['audio_chunks']:
            return
        
        temp_file = None
        try:
            # 将所有chunk合并并保存为临时文件
            audio_data = b''.join(client_info['audio_chunks'])
            
            # 创建临时文件
            temp_file = client_info['temp_dir'] / f"{client_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            temp_file = Path(str(temp_file).replace(":", "_"))  # 文件名中不能有冒号
            
            # 将PCM数据转换为WAV
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            sf.write(str(temp_file), audio_array, self.sample_rate)
            
            logger.info(f"客户端 {client_id} 音频已保存: {temp_file}, 大小: {len(audio_data) / 1024:.1f}KB")
            
            # 发送开始处理通知
            await client_info['websocket'].send_text(json.dumps({
                "type": "processing",
                "message": "开始语音识别...",
                "timestamp": datetime.now().isoformat()
            }, ensure_ascii=False))
            
            # 执行ASR识别
            result = await self.process_audio_file(str(temp_file), client_id)
            
            # 发送识别结果
            await client_info['websocket'].send_text(json.dumps(result, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"识别音频失败: {e}")
            await client_info['websocket'].send_text(json.dumps({
                "success": False,
                "error": f"识别失败: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }, ensure_ascii=False))
        
        finally:
            # 清理临时文件
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
    
    def _cleanup_client(self, client_id: str):
        """清理客户端资源"""
        if client_id in self.active_connections:
            # 清理该客户端的临时文件
            client_info = self.active_connections[client_id]
            temp_dir = client_info.get('temp_dir')
            if temp_dir and temp_dir.exists():
                client_id_safe = client_id.replace(":", "_")
                for f in temp_dir.glob(f"{client_id_safe}_*"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
            
            del self.active_connections[client_id]
            logger.info(f"客户端 {client_id} 资源已清理")


# ============ FastAPI 应用 ============

app = FastAPI(title="FunASR Paraformer-zh Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局服务器实例
server = None

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化服务器"""
    global server
    config_path = Path(__file__).parent / "config.yaml"
    
    # 创建默认配置
    if not config_path.exists():
        default_config = {
            'server': {
                'host': '0.0.0.0',
                'port': 10095,
                'max_connections': 50,
                'sample_rate': 16000
            },
            'models': {
                'asr_model': 'paraformer-zh',
                'vad_model': 'fsmn-vad',
                'punc_model': 'ct-punc',
                'spk_model': 'cam++',
                'device': 'cuda:0',
                'model_hub': 'ms'
            },
            'asr_config': {
                'batch_size_s': 300,
                'hotword': None
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
    
    server = ParaformerServer(str(config_path))

@app.get("/")
async def root():
    """根路径，返回服务器状态"""
    return {
        "status": "running",
        "service": "FunASR Paraformer-zh Server",
        "model": server.config['models']['asr_model'] if server else None,
        "vad_model": server.config['models'].get('vad_model'),
        "punc_model": server.config['models'].get('punc_model'),
        "device": server.config['models'].get('device'),
        "connections": len(server.active_connections) if server else 0,
        "mode": "离线识别模式（接收完整音频后处理）"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.websocket("/ws/asr")
async def websocket_asr(websocket: WebSocket):
    """ASR WebSocket端点"""
    client_id = f"{websocket.client.host}:{websocket.client.port}"
    
    if server:
        await server.handle_websocket_connection(websocket, client_id)
    else:
        await websocket.close(code=1008, reason="Server not initialized")

@app.post("/api/asr/file")
async def asr_file(
    file: UploadFile = File(...),
    hotword: str = Form(None)
):
    """上传文件进行ASR识别"""
    if not server:
        return {"error": "Server not initialized"}
    
    temp_file = None
    try:
        # 保存上传的文件
        content = await file.read()
        
        # 创建临时文件
        temp_dir = Path(tempfile.gettempdir()) / "funasr_upload"
        temp_dir.mkdir(exist_ok=True)
        temp_file = temp_dir / f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        
        with open(temp_file, "wb") as f:
            f.write(content)
        
        # 临时设置热词
        if hotword:
            original_hotword = server.hotword
            server.hotword = hotword
        
        # 执行识别
        result = await server.process_audio_file(str(temp_file))
        
        # 恢复热词
        if hotword:
            server.hotword = original_hotword
        
        result["filename"] = file.filename
        return result
        
    except Exception as e:
        logger.error(f"文件识别失败: {e}")
        return {"success": False, "error": str(e)}
    
    finally:
        # 清理临时文件
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass

@app.post("/api/asr/base64")
async def asr_base64(data: dict):
    """Base64编码的音频数据识别"""
    if not server:
        return {"error": "Server not initialized"}
    
    try:
        audio_base64 = data.get("audio")
        sample_rate = data.get("sample_rate", 16000)
        hotword = data.get("hotword")
        
        if not audio_base64:
            return {"success": False, "error": "No audio data provided"}
        
        # 解码base64
        audio_bytes = base64.b64decode(audio_base64)
        
        temp_file = None
        try:
            # 创建临时文件
            temp_dir = Path(tempfile.gettempdir()) / "funasr_base64"
            temp_dir.mkdir(exist_ok=True)
            temp_file = temp_dir / f"base64_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            
            # 转换为WAV
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            sf.write(str(temp_file), audio_array, sample_rate)
            
            # 临时设置热词
            if hotword:
                original_hotword = server.hotword
                server.hotword = hotword
            
            # 执行识别
            result = await server.process_audio_file(str(temp_file))
            
            # 恢复热词
            if hotword:
                server.hotword = original_hotword
            
            return result
            
        finally:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
                    
    except Exception as e:
        logger.error(f"Base64音频识别失败: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("  FunASR Paraformer-zh 服务器")
    print("="*60)
    print("\n正在启动服务器...")
    print("模型: paraformer-zh (离线高精度识别)")
    print("设备: 自动选择 (优先GPU)")
    print("WebSocket端点: ws://localhost:10095/ws/asr")
    print("HTTP端点: http://localhost:10095")
    print("\n" + "="*60 + "\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=10095,
        log_level="info"
    )
