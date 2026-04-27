import openpyxl
import json
import os
from typing import Dict, Any, List
from app.config import AI_API_KEY, AI_API_URL, AI_MODEL


def read_excel_summary(file_path: str) -> Dict[str, Any]:
    """读取 Excel 内容，生成摘要供 AI 理解"""
    wb = openpyxl.load_workbook(file_path, data_only=True)
    summary = {"sheets": [], "total_rows": 0, "total_cols": 0}

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        # 取前 50 行作为摘要
        sample_rows = rows[:50]
        summary["sheets"].append({
            "name": sheet_name,
            "row_count": ws.max_row,
            "col_count": ws.max_column,
            "headers": [str(c) if c is not None else "" for c in sample_rows[0]] if sample_rows else [],
            "sample": [[str(c) if c is not None else "" for c in row] for row in sample_rows[:10]],
        })
        summary["total_rows"] += ws.max_row

    return summary


def call_ai_modify(excel_summary: Dict, instruction: str) -> List[Dict]:
    """调用 MiniMax AI，分析用户指令，返回修改操作列表"""
    if not AI_API_KEY:
        raise ValueError("未配置 AI API Key，请在环境变量中设置 AI_API_KEY")

    import httpx

    prompt = f"""你是一个 Excel 处理助手。用户有一份 Excel 文件，内容如下：

工作表信息：
{json.dumps(excel_summary, ensure_ascii=False, indent=2)}

用户指令："{instruction}"

请分析用户指令，确定需要执行哪些修改操作。

返回 JSON 格式（数组，每个操作一个对象）：
[
  {{
    "action": "modify_cell | fill_blank | sort | filter | add_row | delete_row",
    "sheet": "工作表名",
    "cell": "A1",           // 单元格地址（action=modify_cell 时）
    "value": "修改后的值",   // 新的值
    "start_row": 1,          // 起始行（sort/filter 时）
    "end_row": 10,           // 结束行
    "column": "A",           // 列
    "sort_order": "asc|desc", // 排序方向
    "condition": "...",      // 筛选条件
    "reason": "为什么这样修改"
  }}
]

注意：
- 只返回 JSON，不要解释
- 确保 action 和相关字段匹配
- 如果指令不明确，返回空数组 []
"""

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            AI_API_URL,
            headers={
                "Authorization": f"Bearer {AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": AI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]

        # 解析 JSON
        try:
            # 尝试提取 JSON 块
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except json.JSONDecodeError:
            raise ValueError(f"AI 返回格式错误：{content[:200]}")


def apply_modifications(file_path: str, operations: List[Dict], output_path: str) -> str:
    """根据 AI 返回的操作列表，修改 Excel 并保存"""
    wb = openpyxl.load_workbook(file_path)
    sheet_map = {s.title: s for s in wb.worksheets}

    for op in operations:
        action = op.get("action")
        sheet_name = op.get("sheet", wb.sheetnames[0])
        ws = sheet_map.get(sheet_name)
        if not ws:
            continue

        if action == "modify_cell":
            cell = op.get("cell")
            value = op.get("value", "")
            if cell:
                ws[cell] = value

        elif action == "fill_blank":
            # 填充空白单元格
            col = op.get("column", "A")
            start_row = op.get("start_row", 1)
            end_row = op.get("end_row", ws.max_row)
            fill_value = op.get("value", "0")
            for row in range(start_row, min(end_row + 1, ws.max_row + 1)):
                cell = ws[f"{col}{row}"]
                if cell.value is None or str(cell.value).strip() == "":
                    cell.value = fill_value

        elif action == "sort":
            # 简单排序（按指定列）
            start_row = op.get("start_row", 2)
            end_row = op.get("end_row", ws.max_row)
            sort_col = op.get("column", "A")
            sort_order = op.get("sort_order", "asc")
            col_idx = openpyxl.utils.column_index_from_string(sort_col)

            rows_data = []
            for row in range(start_row, end_row + 1):
                row_data = [ws.cell(row=row, column=c).value for c in range(1, ws.max_column + 1)]
                rows_data.append(row_data)

            reverse = sort_order == "desc"
            rows_data.sort(key=lambda x: (x[col_idx - 1] is None, x[col_idx - 1] if x[col_idx - 1] is not None else ""), reverse=reverse)

            for i, row in enumerate(range(start_row, end_row + 1)):
                for j, val in enumerate(rows_data[i]):
                    ws.cell(row=row, column=j + 1).value = val

    wb.save(output_path)
    return output_path


def process_excel(file_path: str, instruction: str, output_path: str) -> Dict[str, Any]:
    """完整处理流程：读取 → AI分析 → 执行修改 → 保存"""
    # 1. 读取 Excel 摘要
    summary = read_excel_summary(file_path)

    # 2. 调用 AI 获取修改方案
    operations = call_ai_modify(summary, instruction)

    if not operations:
        return {"success": True, "message": "未检测到需要执行的修改操作", "operations": []}

    # 3. 执行修改
    apply_modifications(file_path, operations, output_path)

    return {
        "success": True,
        "message": f"成功执行 {len(operations)} 项修改",
        "operations": operations,
    }
