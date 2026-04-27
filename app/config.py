import os

# MiniMax API 配置（通过中转渠道）
# 渠道: https://noingfushanquan.online
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_API_URL = os.getenv("AI_API_URL", "https://noingfushanquan.online/v1/chat/completions")
AI_MODEL = os.getenv("AI_MODEL", "mini-max-01")

# COS 配置
COS_SECRET_ID = os.getenv("COS_SECRET_ID", "")
COS_SECRET_KEY = os.getenv("COS_SECRET_KEY", "")
COS_BUCKET = os.getenv("COS_BUCKET", "yanghao-1303848059")
COS_REGION = os.getenv("COS_REGION", "ap-guangzhou")
COS_BASE_URL = os.getenv("COS_BASE_URL", "https://yanghao-1303848059.cos.ap-guangzhou.myqcloud.com")

# 服务配置
UPLOAD_DIR = "/tmp/uploads"
RESULT_DIR = "/tmp/results"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
