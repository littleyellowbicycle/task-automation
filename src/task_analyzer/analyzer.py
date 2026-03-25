from __future__ import annotations

from typing import List, Dict, Any
import re


class TaskAnalyzer:
    # Task analyzer extracts a structured summary from a message

    def __init__(self) -> None:
        pass

    def analyze(self, message: str) -> Dict[str, Any]:
        if not message:
            return {
                "summary": "",
                "tech_stack": [],
                "core_features": [],
                "constraints": [],
                "estimated_complexity": "simple",
            }
        # Enhanced heuristic extraction
        tech_candidates = [
            "Python","Java","Go","JavaScript","TypeScript","React","Vue","Angular",
            "Django","Flask","FastAPI","Node","PostgreSQL","MySQL","MongoDB",
            "Docker","Kubernetes","Redis","RabbitMQ","Kafka"
        ]
        techs = []
        lower = message
        for t in tech_candidates:
            if t.lower() in lower.lower():
                techs.append(t)
        # Features / core points
        core_points = []
        for kw in ["login","authentication","registration","api","db","ci","cd","monitoring","deployment","scaling"]:
            if kw in message.lower():
                core_points.append(kw)
        summary = message[:250] if len(message) > 250 else message
        complexity = "simple"
        if len(message) > 200 and ("complex" in message.lower() or len(core_points) > 2 or len(techs) > 2):
            complexity = "medium"
        if len(message) > 400 or (len(core_points) >= 3 and len(techs) >= 2):
            complexity = "complex"
        result: Dict[str, Any] = {
            "summary": summary,
            "tech_stack": list(dict.fromkeys(techs)),  # preserve order, dedupe
            "core_features": core_points or ["basic functionality"],
            "constraints": [],
            "estimated_complexity": complexity,
        }
        return result
