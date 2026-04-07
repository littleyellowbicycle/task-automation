"""
测试字段映射 - 创建记录后不自动删除，供用户检查
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.feishu_recorder.client import FeishuClient
from src.feishu_recorder.models import TaskRecord, TaskStatus
from datetime import datetime

client = FeishuClient()

record = TaskRecord(
    task_id='TEST_FIELD_MAPPING',
    raw_message='这是一条测试消息，用于检查字段映射是否正确',
    summary='这是任务标题-应该显示在这里',
    tech_stack=['Python', 'FastAPI'],
    core_features=['功能A', '功能B'],
    status=TaskStatus.PENDING,
    created_at=datetime.now(),
)

print('创建测试记录...')
success = client.create_record(record)
print(f'创建结果: {success}')
print(f'Task ID: {record.task_id}')
print('\n请去飞书表格检查以下字段是否正确填充:')
print('  - 任务 ID: TEST_FIELD_MAPPING')
print('  - 任务标题: 这是任务标题-应该显示在这里')
print('  - 任务描述: 这是一条测试消息...')
print('  - 任务完成状态: 未勾选')
print('\n检查完后按回车键删除测试记录...')
input()

print('删除测试记录...')
if client.delete_record(record.task_id):
    print('删除成功!')
else:
    print('删除失败，请手动删除')
