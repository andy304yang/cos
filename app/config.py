import os
from pathlib import Path
from dotenv import load_dotenv

# 自动加载 cos/.env（开发时）；生产环境由 docker 注入，load_dotenv 不会覆盖已有值
load_dotenv(Path(__file__).parent.parent / ".env")

# AI
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_API_URL = os.getenv("AI_API_URL", "https://noingfushanquan.online/v1/chat/completions")
AI_MODEL = os.getenv("AI_MODEL", "MiniMax-M2.7")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "60"))

# COS
COS_SECRET_ID = os.getenv("COS_SECRET_ID", "")
COS_SECRET_KEY = os.getenv("COS_SECRET_KEY", "")
COS_BUCKET = os.getenv("COS_BUCKET", "yanghao-1303848059")
COS_REGION = os.getenv("COS_REGION", "ap-guangzhou")
COS_BASE_URL = os.getenv("COS_BASE_URL", "https://yanghao-1303848059.cos.ap-guangzhou.myqcloud.com")

# 文件存储（绝对路径，禁止硬编码 /Users/xxx）
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/uploads")
RESULT_DIR = os.getenv("RESULT_DIR", "/tmp/results")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
MAX_FILE_SIZE = MAX_UPLOAD_MB * 1024 * 1024

# 版本信息（CI/CD 构建时注入，手动部署时在 .env 中填写）
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
GIT_COMMIT = os.getenv("GIT_COMMIT", "unknown")

# 本地模式：COS 凭证未配置时跳过云存储，结果直接从后端下载
LOCAL_MODE = not bool(COS_SECRET_ID and COS_SECRET_KEY)
