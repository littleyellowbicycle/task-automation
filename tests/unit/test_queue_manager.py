from __future__ import annotations

import pytest

from src.gateway.core.queue_manager import QueueManager, QueueConfig, QueueFullError


class TestQueueManager:
    def setup_method(self):
        self.config = QueueConfig(max_size=5, confirmation_timeout=60)
        self.qm = QueueManager(config=self.config)

    def test_enqueue(self):
        item = self.qm.enqueue("task_1")
        assert item.task_id == "task_1"
        assert self.qm.size == 1

    def test_enqueue_multiple(self):
        self.qm.enqueue("task_1")
        self.qm.enqueue("task_2")
        self.qm.enqueue("task_3")
        assert self.qm.size == 3

    def test_enqueue_full_raises(self):
        for i in range(5):
            self.qm.enqueue(f"task_{i}")
        with pytest.raises(QueueFullError):
            self.qm.enqueue("task_overflow")

    def test_dequeue(self):
        self.qm.enqueue("task_1")
        task_id = self.qm.dequeue()
        assert task_id == "task_1"
        assert self.qm.size == 0
        assert self.qm.current_task == "task_1"

    def test_dequeue_empty_returns_none(self):
        assert self.qm.dequeue() is None

    def test_dequeue_already_processing_returns_none(self):
        self.qm.enqueue("task_1")
        self.qm.dequeue()
        self.qm.enqueue("task_2")
        result = self.qm.dequeue()
        assert result is None

    def test_complete_current_success(self):
        self.qm.enqueue("task_1")
        self.qm.dequeue()
        completed = self.qm.complete_current(success=True)
        assert completed == "task_1"
        assert self.qm.current_task is None
        assert self.qm.stats["total_completed"] == 1

    def test_complete_current_failure(self):
        self.qm.enqueue("task_1")
        self.qm.dequeue()
        completed = self.qm.complete_current(success=False)
        assert completed == "task_1"
        assert self.qm.stats["total_failed"] == 1

    def test_complete_current_no_task(self):
        assert self.qm.complete_current() is None

    def test_cancel_task_in_queue(self):
        self.qm.enqueue("task_1")
        self.qm.enqueue("task_2")
        result = self.qm.cancel_task("task_1")
        assert result is True
        assert self.qm.size == 1
        assert self.qm.stats["total_cancelled"] == 1

    def test_cancel_current_task(self):
        self.qm.enqueue("task_1")
        self.qm.dequeue()
        result = self.qm.cancel_task("task_1")
        assert result is True
        assert self.qm.current_task is None

    def test_cancel_nonexistent_task(self):
        result = self.qm.cancel_task("nonexistent")
        assert result is False

    def test_requeue_task(self):
        self.qm.enqueue("task_1")
        self.qm.dequeue()
        result = self.qm.requeue_task("task_1")
        assert result is True
        assert self.qm.size == 1
        assert self.qm.current_task is None

    def test_requeue_nonexistent(self):
        result = self.qm.requeue_task("nonexistent")
        assert result is False

    def test_requeue_full_queue(self):
        for i in range(5):
            self.qm.enqueue(f"task_{i}")
        result = self.qm.requeue_task("task_0")
        assert result is False

    def test_timeout_task(self):
        self.qm.enqueue("task_1")
        self.qm.dequeue()
        result = self.qm.timeout_task("task_1")
        assert result is True
        assert self.qm.current_task is None
        assert self.qm.stats["total_timeout"] == 1

    def test_timeout_nonexistent(self):
        result = self.qm.timeout_task("nonexistent")
        assert result is False

    def test_get_pending_count(self):
        self.qm.enqueue("task_1")
        self.qm.enqueue("task_2")
        assert self.qm.get_pending_count() == 2

    def test_stats(self):
        self.qm.enqueue("task_1")
        self.qm.dequeue()
        self.qm.complete_current(success=True)
        stats = self.qm.stats
        assert stats["total_enqueued"] == 1
        assert stats["total_dequeued"] == 1
        assert stats["total_completed"] == 1
        assert stats["queue_size"] == 0
        assert stats["max_size"] == 5

    def test_fifo_order(self):
        self.qm.enqueue("first")
        self.qm.enqueue("second")
        self.qm.enqueue("third")
        assert self.qm.dequeue() == "first"
        self.qm.complete_current()
        assert self.qm.dequeue() == "second"

    def test_full_lifecycle(self):
        self.qm.enqueue("task_1")
        self.qm.enqueue("task_2")
        assert self.qm.size == 2

        task_id = self.qm.dequeue()
        assert task_id == "task_1"
        assert self.qm.current_task == "task_1"

        self.qm.complete_current(success=True)
        assert self.qm.current_task is None

        task_id = self.qm.dequeue()
        assert task_id == "task_2"
        self.qm.complete_current(success=False)

        stats = self.qm.stats
        assert stats["total_completed"] == 1
        assert stats["total_failed"] == 1
