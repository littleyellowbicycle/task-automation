from src.task_analyzer import TaskAnalyzer


def test_analyze_basic_message():
    ta = TaskAnalyzer()
    message = "实现用户登录功能，使用 Python Flask，包含邮箱验证码认证"
    out = ta.analyze(message)
    assert isinstance(out, dict)
    assert "summary" in out
    assert "tech_stack" in out
    assert "core_features" in out
    assert isinstance(out["tech_stack"], list)
    assert isinstance(out["core_features"], list)
