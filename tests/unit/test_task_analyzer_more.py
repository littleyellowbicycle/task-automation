from src.task_analyzer import TaskAnalyzer


def test_task_analyzer_moderate_complex_case():
    ta = TaskAnalyzer()
    message = "构建一个 API 服务，使用 FastAPI + PostgreSQL，容器化部署。包含用户认证、数据库迁移和日志监控。"
    result = ta.analyze(message)
    assert isinstance(result, dict)
    assert "summary" in result and isinstance(result["summary"], str)
    assert "tech_stack" in result and isinstance(result["tech_stack"], list)
    assert "core_features" in result and isinstance(result["core_features"], list)
    tech = [t for t in result["tech_stack"] if t.lower() in ("fastapi", "postgresql", "postgresql")]
    assert len(tech) >= 1
    assert result["estimated_complexity"] in ("simple", "medium", "complex")
