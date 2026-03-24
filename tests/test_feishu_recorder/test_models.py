"""Tests for Feishu recorder models."""

import pytest
from datetime import datetime
from src.feishu_recorder.models import TaskRecord, TaskStatus


class TestTaskStatus:
    def test_all_statuses_exist(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.APPROVED.value == "approved"
        assert TaskStatus.EXECUTING.value == "executing"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"


class TestTaskRecord:
    def test_create_record(self):
        record = TaskRecord(
            task_id="test_001",
            raw_message="原始消息",
            summary="摘要",
            tech_stack=["Python"],
            core_features=["功能1"],
        )
        assert record.task_id == "test_001"
        assert record.status == TaskStatus.PENDING
        assert "Python" in record.tech_stack

    def test_to_dict(self):
        record = TaskRecord(
            task_id="test_001",
            raw_message="原始消息",
            summary="摘要",
        )
        data = record.to_dict()
        assert data["task_id"] == "test_001"
        assert data["status"] == "pending"

    def test_from_dict(self):
        data = {
            "task_id": "test_002",
            "raw_message": "消息",
            "summary": "摘要",
            "tech_stack": "Python,Flask",
            "status": "completed",
        }
        record = TaskRecord.from_dict(data)
        assert record.task_id == "test_002"
        assert "Python" in record.tech_stack
        assert "Flask" in record.tech_stack
        assert record.status == TaskStatus.COMPLETED
