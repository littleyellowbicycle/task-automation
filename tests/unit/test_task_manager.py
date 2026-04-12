from __future__ import annotations

import pytest

from src.gateway.core.task_manager import TaskManager
from src.gateway.models.tasks import TaskStatus, AnalysisResult, ExecutionResultData, RecordingResultData


class TestTaskManager:
    def setup_method(self):
        self.tm = TaskManager()

    def test_create_task(self):
        task = self.tm.create_task("hello world")
        assert task.task_id.startswith("task_")
        assert task.status == TaskStatus.RECEIVED
        assert task.raw_message == "hello world"

    def test_create_task_with_standard_message(self):
        msg = {"msg_id": "m1", "content": "test"}
        task = self.tm.create_task("test", standard_message=msg)
        assert task.standard_message == msg

    def test_get_task(self):
        created = self.tm.create_task("find me")
        found = self.tm.get_task(created.task_id)
        assert found is created

    def test_get_task_not_found(self):
        assert self.tm.get_task("nonexistent") is None

    def test_update_status(self):
        task = self.tm.create_task("status test")
        updated = self.tm.update_status(task.task_id, TaskStatus.FILTERING)
        assert updated.status == TaskStatus.FILTERING

    def test_update_status_not_found(self):
        result = self.tm.update_status("nonexistent", TaskStatus.FILTERING)
        assert result is None

    def test_update_status_with_error(self):
        task = self.tm.create_task("error test")
        self.tm.update_status(task.task_id, TaskStatus.FAILED, error="something broke")
        found = self.tm.get_task(task.task_id)
        assert found.error_message == "something broke"

    def test_update_status_completed_increments_stats(self):
        task = self.tm.create_task("complete me")
        self.tm.update_status(task.task_id, TaskStatus.COMPLETED)
        assert self.tm.stats["total_completed"] == 1

    def test_update_status_failed_increments_stats(self):
        task = self.tm.create_task("fail me")
        self.tm.update_status(task.task_id, TaskStatus.FAILED)
        assert self.tm.stats["total_failed"] == 1

    def test_update_status_cancelled_increments_stats(self):
        task = self.tm.create_task("cancel me")
        self.tm.update_status(task.task_id, TaskStatus.CANCELLED)
        assert self.tm.stats["total_cancelled"] == 1

    def test_set_analysis_result(self):
        task = self.tm.create_task("analyze me")
        analysis = AnalysisResult(is_task=True, summary="test summary", complexity="simple")
        result = self.tm.set_analysis_result(task.task_id, analysis)
        assert result.analysis_result.summary == "test summary"

    def test_set_analysis_result_not_found(self):
        analysis = AnalysisResult(is_task=True)
        assert self.tm.set_analysis_result("nonexistent", analysis) is None

    def test_set_decision(self):
        task = self.tm.create_task("decide me")
        self.tm.set_decision(task.task_id, "approve")
        assert self.tm.get_task(task.task_id).decision == "approve"

    def test_set_execution_result(self):
        task = self.tm.create_task("execute me")
        exec_result = ExecutionResultData(success=True, stdout="done")
        self.tm.set_execution_result(task.task_id, exec_result)
        assert self.tm.get_task(task.task_id).execution_result.stdout == "done"

    def test_set_recording_result(self):
        task = self.tm.create_task("record me")
        rec_result = RecordingResultData(success=True, record_id="rec_001")
        self.tm.set_recording_result(task.task_id, rec_result)
        assert self.tm.get_task(task.task_id).recording_result.record_id == "rec_001"

    def test_list_tasks(self):
        self.tm.create_task("task 1")
        self.tm.create_task("task 2")
        self.tm.create_task("task 3")
        result = self.tm.list_tasks()
        assert result["total"] == 3
        assert len(result["items"]) == 3

    def test_list_tasks_pagination(self):
        for i in range(5):
            self.tm.create_task(f"task {i}")
        result = self.tm.list_tasks(page=1, page_size=2)
        assert result["total"] == 5
        assert len(result["items"]) == 2

    def test_list_tasks_filter_by_status(self):
        t1 = self.tm.create_task("active")
        t2 = self.tm.create_task("done")
        self.tm.update_status(t2.task_id, TaskStatus.COMPLETED)
        result = self.tm.list_tasks(status=TaskStatus.COMPLETED)
        assert result["total"] == 1

    def test_get_tasks_by_status(self):
        t1 = self.tm.create_task("a")
        t2 = self.tm.create_task("b")
        self.tm.update_status(t1.task_id, TaskStatus.FILTERING)
        self.tm.update_status(t2.task_id, TaskStatus.COMPLETED)
        filtering = self.tm.get_tasks_by_status(TaskStatus.FILTERING)
        assert len(filtering) == 1
        assert filtering[0].task_id == t1.task_id

    def test_stats(self):
        self.tm.create_task("s1")
        t2 = self.tm.create_task("s2")
        self.tm.update_status(t2.task_id, TaskStatus.COMPLETED)
        stats = self.tm.stats
        assert stats["total_created"] == 2
        assert stats["total_completed"] == 1
        assert stats["active_tasks"] == 2

    def test_task_to_dict(self):
        task = self.tm.create_task("dict test")
        d = task.to_dict()
        assert d["task_id"] == task.task_id
        assert d["status"] == "received"
        assert d["raw_message"] == "dict test"
        assert d["summary"] is None

    def test_task_to_dict_with_analysis(self):
        task = self.tm.create_task("with analysis")
        self.tm.set_analysis_result(task.task_id, AnalysisResult(summary="my summary"))
        d = task.to_dict()
        assert d["summary"] == "my summary"
