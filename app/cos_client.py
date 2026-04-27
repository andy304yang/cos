import os
from qcloud_cos import CosConfig, CosS3Client
from app.config import COS_SECRET_ID, COS_SECRET_KEY, COS_BUCKET, COS_REGION, COS_BASE_URL


def get_cos_client() -> CosS3Client:
    config = CosConfig(
        Region=COS_REGION,
        SecretId=COS_SECRET_ID,
        SecretKey=COS_SECRET_KEY,
    )
    return CosS3Client(config)


def upload_file_to_cos(local_path: str, cos_key: str) -> str:
    """上传本地文件到 COS，返回公开访问 URL"""
    client = get_cos_client()
    client.put_object_from_local_file(
        Bucket=COS_BUCKET,
        LocalFilePath=local_path,
        Key=cos_key,
    )
    return f"{COS_BASE_URL}/{cos_key}"


def download_file_from_cos(cos_key: str, local_path: str) -> bool:
    """从 COS 下载文件到本地"""
    client = get_cos_client()
    try:
        response = client.get_object(
            Bucket=COS_BUCKET,
            Key=cos_key,
        )
        response["Body"].get_stream_to_file(local_path)
        return True
    except Exception:
        return False


def delete_cos_file(cos_key: str) -> bool:
    """删除 COS 文件"""
    client = get_cos_client()
    try:
        client.delete_object(Bucket=COS_BUCKET, Key=cos_key)
        return True
    except Exception:
        return False


def get_public_url(cos_key: str) -> str:
    """生成公开访问 URL"""
    return f"{COS_BASE_URL}/{cos_key}"
