import os
from pathlib import Path
from dotenv import load_dotenv

# 自动加载 cos/.env（开发时）；生产环境由 docker 注入，load_dotenv 不会覆盖已有值
load_dotenv(Path(__file__).parent.parent / ".env")

AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_API_URL = os.getenv("AI_API_URL", "https://noingfushanquan.online")
AI_MODEL = os.getenv("AI_MODEL", "mini-max-01")

COS_SECRET_ID = os.getenv("COS_SECRET_ID", "")
COS_SECRET_KEY = os.getenv("COS_SECRET_KEY", "")
COS_BUCKET = os.getenv("COS_BUCKET", "yanghao-1303848059")
COS_REGION = os.getenv("COS_REGION", "ap-guangzhou")
COS_BASE_URL = os.getenv("COS_BASE_URL", "https://yanghao-1303848059.cos.ap-guangzhou.myqcloud.com")

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/uploads")
RESULT_DIR = os.getenv("RESULT_DIR", "/tmp/results")
MAX_FILE_SIZE = 50 * 1024 * 1024

# 本地模式：COS 凭证未配置时跳过云存储，结果直接从后端下载
LOCAL_MODE = not bool(COS_SECRET_ID and COS_SECRET_KEY)
