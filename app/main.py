import os
import shutil
import threading
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import UPLOAD_DIR, RESULT_DIR, MAX_FILE_SIZE
from app.cos_client import upload_file_to_cos, get_public_url
from app.excel_processor import process_excel
from app.task_manager import TaskManager
from app.models import TaskStatus

# 确保目录存在
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(RESULT_DIR).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Excel 处理后端", lifespan=lifespan)

# CORS 允许 Next.js 前端跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def process_task_background(task_id: str, instruction: str):
    """后台线程：处理 Excel 文件"""
    task = TaskManager.get_task(task_id)
    if not task:
        return

    TaskManager.update_task(task_id, status=TaskStatus.PROCESSING, instruction=instruction)

    try:
        result_filename = f"result_{task.filename}"
        output_path = os.path.join(RESULT_DIR, f"{task_id}_{result_filename}")

        # 调用 AI 处理 Excel
        result = process_excel(task.local_path, instruction, output_path)

        if result.get("success") and os.path.exists(output_path):
            # 上传结果到 COS
            result_cos_key = f"results/{task.user_id}/{task_id}/{result_filename}"
            result_url = upload_file_to_cos(output_path, result_cos_key)
            TaskManager.update_task(
                task_id,
                status=TaskStatus.DONE,
                result_url=result_url,
                result_cos_key=result_cos_key,
            )
        else:
            TaskManager.update_task(
                task_id,
                status=TaskStatus.FAILED,
                error=result.get("message", "处理失败"),
            )
    except Exception as e:
        TaskManager.update_task(task_id, status=TaskStatus.FAILED, error=str(e))
    finally:
        # 清理上传的源文件
        TaskManager.delete_task_files(task_id)


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Form(...),
):
    """上传 Excel 文件到 COS，返回 task_id"""
    # 校验文件类型
    allowed = {".xlsx", ".xls", ".csv"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"不支持的文件格式，仅支持：{allowed}")

    # 保存到本地
    local_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file.filename}")
    with open(local_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 上传到 COS
    cos_key = f"uploads/{user_id}/{file.filename}"
    try:
        upload_file_to_cos(local_path, cos_key)
    except Exception as e:
        raise HTTPException(500, f"COS 上传失败：{str(e)}")

    # 创建任务
    task = TaskManager.create_task(user_id, file.filename, local_path, cos_key)

    return {
        "task_id": task.task_id,
        "user_id": user_id,
        "filename": file.filename,
        "status": task.status.value,
        "message": "文件上传成功，请提交处理指令",
    }


@app.post("/api/process")
async def process_file(
    task_id: str = Form(...),
    user_id: str = Form(...),
    instruction: str = Form(...),
):
    """提交处理指令，触发后台 AI 处理"""
    task = TaskManager.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    # 安全校验：只能处理自己的文件
    if task.user_id != user_id:
        raise HTTPException(403, "无权访问此文件")

    if task.status == TaskStatus.PROCESSING:
        raise HTTPException(400, "任务正在处理中")

    if task.status == TaskStatus.DONE:
        raise HTTPException(400, "任务已完成，请直接下载")

    # 启动后台处理
    threading.Thread(
        target=process_task_background,
        args=(task_id, instruction),
        daemon=True,
    ).start()

    return {
        "task_id": task_id,
        "status": TaskStatus.PROCESSING.value,
        "message": "任务已提交，AI 正在处理中，请稍后查询结果",
    }


@app.get("/api/task/{task_id}")
async def get_task_status(
    task_id: str,
    user_id: str = Query(...),
):
    """查询任务状态和结果"""
    task = TaskManager.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    if task.user_id != user_id:
        raise HTTPException(403, "无权访问此文件")

    return task.to_dict()


@app.get("/api/download/{task_id}")
async def download_result(
    task_id: str,
    user_id: str = Query(...),
):
    """下载处理结果"""
    task = TaskManager.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    if task.user_id != user_id:
        raise HTTPException(403, "无权访问此文件")

    if task.status != TaskStatus.DONE or not task.result_url:
        raise HTTPException(400, "任务未完成或无结果文件")

    # 返回 COS 公开链接，前端直接跳转下载
    return {"download_url": task.result_url, "filename": f"result_{task.filename}"}


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
