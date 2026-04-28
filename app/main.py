import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    UPLOAD_DIR, RESULT_DIR, MAX_FILE_SIZE, MAX_UPLOAD_MB,
    LOCAL_MODE, APP_VERSION, GIT_COMMIT, AI_TIMEOUT,
)
from app.cos_client import upload_file_to_cos
from app.excel_processor import process_excel
from app.task_manager import TaskManager
from app.models import TaskStatus

Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(RESULT_DIR).mkdir(parents=True, exist_ok=True)

_RESULT_DIR_RESOLVED = Path(RESULT_DIR).resolve()


def _sanitize_filename(name: str) -> str:
    """去掉目录分隔符，替换非安全字符，限制长度。防路径穿越。"""
    name = Path(name).name          # 剥掉所有目录部分
    name = re.sub(r"[^\w.\-]", "_", name)
    return name[:200] or "upload"


def _check_storage_writable(path: str) -> bool:
    probe = os.path.join(path, ".write_probe")
    try:
        with open(probe, "w") as f:
            f.write("")
        os.remove(probe)
        return True
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Excel 处理后端", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── 后台处理（业务逻辑不变）────────────────────────────────────────

def process_task_background(task_id: str, instruction: str):
    task = TaskManager.get_task(task_id)
    if not task:
        return

    TaskManager.update_task(task_id, status=TaskStatus.PROCESSING, instruction=instruction)

    try:
        base = Path(task.filename).stem
        result_filename = f"result_{base}.xlsx"
        output_path = os.path.join(RESULT_DIR, f"{task_id}_{result_filename}")

        result = process_excel(task.local_path, instruction, output_path)

        if result.get("success") and os.path.exists(output_path):
            if LOCAL_MODE:
                TaskManager.update_task(
                    task_id,
                    status=TaskStatus.DONE,
                    result_url=f"/api/download/{task_id}",
                    result_local_path=output_path,
                )
            else:
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
        TaskManager.delete_task_files(task_id)


# ─── API 路由 ────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Form(...),
):
    # 文件类型校验
    allowed = {".xlsx", ".xls", ".csv"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"不支持的文件格式，仅支持：{', '.join(allowed)}")

    # 读取内容并校验大小（先读到内存，避免大文件落盘后才发现超限）
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"文件过大，最大支持 {MAX_UPLOAD_MB} MB")

    # 安全文件名
    safe_name = _sanitize_filename(file.filename or "upload")
    local_path = os.path.join(UPLOAD_DIR, f"{task_id_prefix(user_id)}_{safe_name}")

    try:
        with open(local_path, "wb") as f:
            f.write(content)
    except OSError as e:
        raise HTTPException(500, f"文件写入失败：{e.strerror}")

    cos_key = ""
    if not LOCAL_MODE:
        cos_key = f"uploads/{user_id}/{safe_name}"
        try:
            upload_file_to_cos(local_path, cos_key)
        except Exception as e:
            raise HTTPException(500, f"COS 上传失败：{str(e)}")

    task = TaskManager.create_task(user_id, safe_name, local_path, cos_key)

    return {
        "task_id": task.task_id,
        "user_id": user_id,
        "filename": safe_name,
        "status": task.status.value,
        "message": "文件上传成功，请提交处理指令",
    }


def task_id_prefix(user_id: str) -> str:
    """生成上传文件的唯一前缀，避免同名文件覆盖。"""
    import uuid
    return str(uuid.uuid4())[:8]


@app.post("/api/process")
async def process_file(
    task_id: str = Form(...),
    user_id: str = Form(...),
    instruction: str = Form(...),
):
    task = TaskManager.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    if task.user_id != user_id:
        raise HTTPException(403, "无权访问此文件")

    if task.status == TaskStatus.PROCESSING:
        raise HTTPException(400, "任务正在处理中")

    if task.status == TaskStatus.DONE:
        raise HTTPException(400, "任务已完成，请直接下载")

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
    task = TaskManager.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    if task.user_id != user_id:
        raise HTTPException(403, "无权访问此文件")

    if task.status != TaskStatus.DONE:
        raise HTTPException(400, "任务未完成")

    if LOCAL_MODE:
        result_path = task.result_local_path
        if not result_path:
            raise HTTPException(404, "结果文件路径未记录")

        # 路径穿越防护：结果文件必须在 RESULT_DIR 内
        resolved = Path(result_path).resolve()
        if not str(resolved).startswith(str(_RESULT_DIR_RESOLVED)):
            raise HTTPException(403, "非法文件路径")

        if not resolved.exists():
            raise HTTPException(404, "结果文件不存在，可能已过期")

        # 直接读取字节返回，比 FileResponse 在 Docker/Linux 下更可靠
        try:
            file_bytes = resolved.read_bytes()
        except OSError as e:
            raise HTTPException(500, f"文件读取失败：{e.strerror}")

        dl_name = f"result_{Path(task.filename).stem}.xlsx"
        return Response(
            content=file_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{dl_name}"'},
        )
    else:
        if not task.result_cos_key:
            raise HTTPException(400, "无结果文件 COS key")
        try:
            from app.cos_client import get_signed_download_url
            signed_url = get_signed_download_url(task.result_cos_key, expires=3600)
        except Exception as e:
            err = str(e)
            if "NoSuchKey" in err:
                raise HTTPException(404, "结果文件不存在，可能已过期或被删除")
            if "AccessDenied" in err:
                raise HTTPException(502, "COS 访问被拒绝，请检查签名配置")
            raise HTTPException(500, f"签名 URL 生成失败：{err}")
        return RedirectResponse(url=signed_url, status_code=302)


@app.get("/api/health")
async def health_check():
    upload_ok = _check_storage_writable(UPLOAD_DIR)
    result_ok = _check_storage_writable(RESULT_DIR)
    return {
        "status": "ok",
        "version": APP_VERSION,
        "commit": GIT_COMMIT,
        "mode": "local" if LOCAL_MODE else "cos",
        "storageWritable": upload_ok and result_ok,
        "uploadDir": Path(UPLOAD_DIR).name,   # 只返回 basename，不暴露绝对路径
        "resultDir": Path(RESULT_DIR).name,
        "aiTimeout": AI_TIMEOUT,
        "time": datetime.now(timezone.utc).isoformat(),
    }
