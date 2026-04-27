# Excel 智能处理后端

FastAPI 后端服务，提供 Excel 文件上传、AI 智能修改、COS 存储、多用户隔离功能。

## 系统架构

```
用户浏览器
    │
    ▼
┌─────────────────────────────────────────────┐
│              Nginx (80/443)                  │
│   /api/* → backend:8000                     │
│   /*   → nextjs:3000                        │
└─────────────────────────────────────────────┘
    │                        │
    ▼                        ▼
┌──────────────┐      ┌──────────────┐
│   FastAPI    │      │   Next.js    │
│  (后端 :8000)│      │  (前端 :3000) │
└──────┬───────┘      └──────────────┘
       │
       ▼
┌──────────────────────────────────┐
│        腾讯云 COS                  │
│   上传文件 / 结果文件存储          │
│   桶: yanghao-1303848059         │
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│     DeepSeek API (AI 处理)        │
│   渠道: https://noingfushanquan.online │
└──────────────────────────────────┘
```

## 部署地址

- **API 基础地址**: `http://81.71.29.84/api`
- **前端地址**: `http://81.71.29.84`

## 接口文档

Base URL: `http://81.71.29.84/api`

---

### 1. 健康检查

**GET** `/api/health`

检查服务是否正常运行。

**响应示例**
```json
{ "status": "ok" }
```

---

### 2. 上传文件

**POST** `/api/upload`

上传 Excel 文件到 COS，服务器存储后返回 `task_id`。

**请求格式**: `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | ✅ | Excel 文件，支持 .xlsx / .xls / .csv |
| user_id | string | ✅ | 用户唯一标识（由前端生成 UUID） |

**响应示例** `200 OK`
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": "user-uuid-xxx",
  "filename": "data.xlsx",
  "status": "uploaded",
  "message": "文件上传成功，请提交处理指令"
}
```

**错误响应** `400 Bad Request`
```json
{ "detail": "不支持的文件格式，仅支持：{'.xlsx', '.xls', '.csv'}" }
```

---

### 3. 提交处理

**POST** `/api/process`

提交 AI 处理指令，启动后台任务。

**请求格式**: `application/x-www-form-urlencoded`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | ✅ | 上一步返回的 task_id |
| user_id | string | ✅ | 用户唯一标识 |
| instruction | string | ✅ | 修改指令，自然语言描述 |

**instruction 示例**:
- `将 A 列的所有空白单元格填充为 0`
- `把第 3 行到第 10 行按金额从大到小排序`
- `删除 B 列为空的行`
- `在最后新增一列，列名为"总计"，值为 A 列 + B 列`

**响应示例** `200 OK`
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "processing",
  "message": "任务已提交，AI 正在处理中，请稍后查询结果"
}
```

**错误响应**
- `404`: 任务不存在
- `403`: 无权访问此文件
- `400`: 任务正在处理中 / 任务已完成

---

### 4. 查询状态

**GET** `/api/task/{task_id}`

轮询任务处理状态，结果完成后返回下载链接。

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| task_id | string | 任务 ID |

**Query 参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | ✅ | 用户唯一标识 |

**响应示例 — 处理中**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": "user-uuid-xxx",
  "status": "processing",
  "filename": "data.xlsx",
  "instruction": "将 A 列空白填 0",
  "result_url": null,
  "error": null
}
```

**响应示例 — 已完成**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": "user-uuid-xxx",
  "status": "done",
  "filename": "data.xlsx",
  "instruction": "将 A 列空白填 0",
  "result_url": "https://yanghao-1303848059.cos.ap-guangzhou.myqcloud.com/results/user-uuid-xxx/a1b2c3d4.../result_data.xlsx",
  "error": null
}
```

**响应示例 — 失败**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": "user-uuid-xxx",
  "status": "failed",
  "filename": "data.xlsx",
  "instruction": "将 A 列空白填 0",
  "result_url": null,
  "error": "AI 处理失败：Sheet 名不存在"
}
```

**status 枚举值**: `uploaded` | `processing` | `done` | `failed`

---

### 5. 下载结果

**GET** `/api/download/{task_id}`

获取处理结果的 COS 公开访问链接，前端直接跳转下载。

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| task_id | string | 任务 ID |

**Query 参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | ✅ | 用户唯一标识 |

**响应示例** `200 OK`
```json
{
  "download_url": "https://yanghao-1303848059.cos.ap-guangzhou.myqcloud.com/results/user-uuid-xxx/a1b2c3d4.../result_data.xlsx",
  "filename": "result_data.xlsx"
}
```

**错误响应**
- `400`: 任务未完成或无结果文件
- `403`: 无权访问此文件
- `404`: 任务不存在

---

## 多用户隔离机制

每个用户在前端首次访问时生成一个 UUID 作为 `user_id`，所有文件操作均以此 ID 为隔离依据：

- **上传路径**: `cos://uploads/{user_id}/{filename}`
- **结果路径**: `cos://results/{user_id}/{task_id}/{result_filename}`

用户只能通过自己的 `task_id` + `user_id` 组合查询和下载文件，无法访问他人的文件。

---

## 前端对接示例

```javascript
const API_BASE = 'http://81.71.29.84/api'

// 1. 生成用户 ID（首次访问时）
const userId = localStorage.getItem('user_id') || crypto.randomUUID()
localStorage.setItem('user_id', userId)

// 2. 上传文件
const formData = new FormData()
formData.append('file', fileInput.files[0])
formData.append('user_id', userId)

const uploadRes = await fetch(`${API_BASE}/upload`, {
  method: 'POST',
  body: formData,
})
const { task_id } = await uploadRes.json()

// 3. 提交处理指令
const processRes = await fetch(`${API_BASE}/process`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({ task_id, user_id: userId, instruction }),
})
const processData = await processRes.json()

// 4. 轮询状态（建议 2-3 秒轮一次）
const poll = async () => {
  const res = await fetch(`${API_BASE}/task/${task_id}?user_id=${userId}`)
  const data = await res.json()
  if (data.status === 'done') {
    // 5. 下载结果
    window.location.href = data.result_url
  } else if (data.status === 'failed') {
    alert('处理失败：' + data.error)
  } else {
    setTimeout(poll, 2000)
  }
}
poll()
```

---

## 环境变量

| 变量 | 必填 | 说明 | 默认值 |
|------|------|------|--------|
| COS_SECRET_ID | ✅ | 腾讯云 SecretId | — |
| COS_SECRET_KEY | ✅ | 腾讯云 SecretKey | — |
| COS_BUCKET | — | COS Bucket 名称 | yanghao-1303848059 |
| COS_REGION | — | COS 地域 | ap-guangzhou |
| COS_BASE_URL | — | COS 公开访问基础地址 | https://yanghao-1303848059.cos.ap-guangzhou.myqcloud.com |
| DEEPSEEK_API_KEY | ✅ | DeepSeek API Key | — |
| DEEPSEEK_API_URL | — | DeepSeek API 地址 | https://noingfushanquan.online/v1/chat/completions |
| DEEPSEEK_MODEL | — | 模型名称 | deepseek-chat |

> **注意**: DEEPSEEK_API_KEY 使用用户提供的渠道地址 `https://noingfushanquan.online`，非官方地址。

---

## AI 处理流程

```
1. 读取 Excel 文件内容（openpyxl）
2. 生成数据摘要（行列数、列名、样本数据）
3. 将摘要 + 用户指令发送给 DeepSeek AI
4. AI 返回结构化修改方案（JSON 格式）
5. openpyxl 执行修改操作
6. 结果文件上传到 COS
7. 返回公开下载链接
```

---

## 部署

### Docker 部署（推荐）

```bash
# 复制环境变量文件并填写
cp .env.example .env
nano .env   # 填入 COS_SECRET_ID, COS_SECRET_KEY, DEEPSEEK_API_KEY

# 启动所有服务（前端 + 后端 + Nginx）
docker compose up -d --build

# 查看日志
docker compose logs -f backend
```

### 目录结构

```
dream/
├── backend/              # 本项目，FastAPI 后端
│   ├── app/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .env.example
│   └── requirements.txt
├── .next/               # Next.js 前端构建产物（standalone）
├── public/
├── nginx/
│   ├── nginx.conf
│   └── certs/           # SSL 证书
└── docker-compose.yml    # 根目录编排（前端 + 后端 + nginx）
```

---

## 本地开发

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 复制环境变量
cp .env.example .env
# 填入 DEEPSEEK_API_KEY 等

# 启动服务
uvicorn app.main:app --reload --port 8000
```

API 文档: http://localhost:8000/docs

---

## 技术栈

- **后端框架**: FastAPI + Uvicorn
- **Excel 处理**: openpyxl
- **AI 模型**: DeepSeek Chat API (渠道)
- **文件存储**: 腾讯云 COS
- **容器化**: Docker + Docker Compose
- **反向代理**: Nginx
