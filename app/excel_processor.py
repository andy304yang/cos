import json
import os
import pandas as pd
from typing import Dict, Any
from app.config import AI_API_KEY, AI_API_URL, AI_MODEL


def _read_file(file_path: str) -> pd.DataFrame:
    if file_path.lower().endswith(".csv"):
        return pd.read_csv(file_path)
    return pd.read_excel(file_path)


def _build_df_info(df: pd.DataFrame) -> str:
    lines = [
        f"共 {len(df)} 行，{len(df.columns)} 列",
        f"列名（按顺序）：{list(df.columns)}",
        "前5行数据（dict格式）：",
    ]
    for _, row in df.head(5).iterrows():
        lines.append("  " + str(dict(row)))
    return "\n".join(lines)


def _call_ai_for_code(df_info: str, instruction: str) -> str:
    """让 AI 生成 pandas 代码来处理任意自然语言指令"""
    if not AI_API_KEY:
        raise ValueError("未配置 AI_API_KEY")

    import httpx

    prompt = f"""你是一个 Excel/数据处理专家，使用 Python pandas 完成用户的数据处理需求。

DataFrame 信息：
{df_info}

用户指令："{instruction}"

请生成 Python 代码。约束：
1. DataFrame 已经加载为变量 `df`，直接操作它
2. 操作结果必须赋值回 `df`（例如 `df = df.drop(...)`）
3. 只能使用 `pd`（pandas）和 Python 内置函数，不能 import 其他库
4. 不要读写文件，不要 print
5. 只返回纯 Python 代码，不要任何解释和 markdown

示例（删除第一列）：
df = df.iloc[:, 1:]

示例（填充空值为0）：
df['金额'] = df['金额'].fillna(0)
"""

    with httpx.Client(timeout=60.0, trust_env=False) as client:
        try:
            response = client.post(
                AI_API_URL,
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code in (401, 403):
                raise ValueError("AI API Key 无效或无权限，请检查 .env 中的 AI_API_KEY 配置")
            if code == 429:
                raise ValueError("AI API 请求频率超限，请稍等几秒后重试")
            if code >= 500:
                raise ValueError(f"AI 服务暂时不可用（HTTP {code}），请稍后重试")
            raise ValueError(f"AI 请求失败（HTTP {code}）")
        except httpx.TimeoutException:
            raise ValueError("AI 请求超时（60s），文件可能过大，请精简内容后重试")
        content = response.json()["choices"][0]["message"]["content"]

    # 去掉 markdown 代码块
    if "```python" in content:
        content = content.split("```python")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    return content.strip()


def _execute_code(df: pd.DataFrame, code: str) -> pd.DataFrame:
    """在受限命名空间中执行 AI 生成的 pandas 代码"""
    safe_builtins = {
        "len": len, "range": range, "list": list, "dict": dict, "tuple": tuple,
        "str": str, "int": int, "float": float, "bool": bool,
        "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
        "enumerate": enumerate, "zip": zip, "sorted": sorted,
        "None": None, "True": True, "False": False,
    }
    namespace = {
        "df": df.copy(),
        "pd": pd,
        "__builtins__": safe_builtins,
    }
    exec(code, namespace)  # noqa: S102
    result = namespace.get("df")
    if not isinstance(result, pd.DataFrame):
        raise ValueError("AI 生成的代码没有将结果赋值回 df")
    return result


def process_excel(file_path: str, instruction: str, output_path: str) -> Dict[str, Any]:
    """完整流程：读文件 → AI 生成代码 → 执行 → 保存 xlsx"""
    df = _read_file(file_path)
    df_info = _build_df_info(df)

    code = _call_ai_for_code(df_info, instruction)

    if not code:
        df.to_excel(output_path, index=False, engine="openpyxl")
        return {"success": True, "message": "AI 未生成任何操作代码", "code": ""}

    result_df = _execute_code(df, code)
    result_df.to_excel(output_path, index=False, engine="openpyxl")

    return {"success": True, "message": "处理完成", "code": code}
