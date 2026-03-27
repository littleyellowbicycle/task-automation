from src.feishu_recorder.feishu_bridge import FeishuBridge
from src.feishu_recorder.models import TaskRecord, TaskStatus


def test_feishu_bridge_write_record():
    bridge = FeishuBridge()
    rec = TaskRecord(
        task_id="bridge-001",
        raw_message="test message",
        summary="test summary",
        tech_stack=["Python"],
        core_features=["login"],
        status=TaskStatus.PENDING,
    )
    assert bridge.write_record(rec) is True
