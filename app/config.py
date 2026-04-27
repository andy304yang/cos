import os

# COS 配置
COS_SECRET_ID = os.getenv("COS_SECRET_ID", "AKIDRUQCpIbJsIYdZq5B9xdDesWyBAvRjvui")
COS_SECRET_KEY = os.getenv("COS_SECRET_KEY", "c093iOq44rQkqiY9VdXDdoRs53nKdhjZ")
COS_BUCKET = os.getenv("COS_BUCKET", "yanghao-1303848059")
COS_REGION = os.getenv("COS_REGION", "ap-guangzhou")
COS_BASE_URL = os.getenv("COS_BASE_URL", "https://yanghao-1303848059.cos.ap-guangzhou.myqcloud.com")

# AI 配置（DeepSeek）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 服务配置
UPLOAD_DIR = "/tmp/uploads"
RESULT_DIR = "/tmp/results"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
