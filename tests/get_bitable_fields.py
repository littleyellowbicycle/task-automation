"""
查询飞书多维表格字段结构

使用方法:
python tests/get_bitable_fields.py
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import requests


def get_fields():
    """获取多维表格字段"""
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    bitable_token = os.getenv("FEISHU_BITABLE_TOKEN")
    table_id = os.getenv("FEISHU_TABLE_ID")
    
    if not all([app_id, app_secret, bitable_token, table_id]):
        print("请先配置所有飞书相关环境变量")
        return
    
    # 获取 token
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    response = requests.post(url, json={
        "app_id": app_id,
        "app_secret": app_secret,
    })
    
    data = response.json()
    if data.get("code") != 0:
        print(f"获取 token 失败: {data}")
        return
    
    token = data.get("tenant_access_token")
    print(f"Token 获取成功\n")
    
    # 获取表格字段
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{bitable_token}/tables/{table_id}/fields"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    data = response.json()
    
    if data.get("code") == 0:
        fields = data.get("data", {}).get("items", [])
        print(f"表格字段 (共 {len(fields)} 个):\n")
        print(f"{'字段名':<20} {'字段ID':<25} {'类型':<15}")
        print("-" * 60)
        for field in fields:
            name = field.get("field_name", "")
            field_id = field.get("field_id", "")
            field_type = field.get("type", 0)
            type_names = {
                1: "文本", 2: "数字", 3: "单选", 4: "多选",
                5: "日期", 7: "复选框", 11: "人员", 13: "电话",
                15: "URL", 17: "附件", 18: "关联", 19: "公式",
                20: "双向关联", 21: "位置", 22: "群组", 23: "条码",
                1001: "创建时间", 1002: "修改时间", 1003: "创建人", 1004: "修改人"
            }
            type_name = type_names.get(field_type, f"未知({field_type})")
            print(f"{name:<20} {field_id:<25} {type_name:<15}")
        
        print("\n建议: 请确保表格有以下字段:")
        print("  - task_id (文本)")
        print("  - raw_message (文本)")
        print("  - summary (文本)")
        print("  - tech_stack (文本)")
        print("  - core_features (文本)")
        print("  - status (文本)")
        print("  - code_repo_url (文本)")
    else:
        print(f"获取字段失败: {data}")


if __name__ == "__main__":
    get_fields()
