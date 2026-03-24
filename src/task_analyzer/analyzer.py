from __future__ import annotations

from typing import List, Dict, Any
import re


class TaskAnalyzer:
    """Simple task analyzer that extracts a summary, tech_stack and core_features from a message."""

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
        # Very lightweight extraction rules
        techs = re.findall(r"(Python|JavaScript|Go|Java|C\+\+|TypeScript|React|Django|Flask|Vue|Redux|Node)\w*", message, flags=re.IGNORECASE)
        features = []
        for kw in ["login", "authentication", "registration", "api", "db", "mesh"]:
            if kw in message.lower():
                features.append(kw)
        summary = message[:200] if len(message) > 200 else message
        result = {
            "summary": summary,
            "tech_stack": list({t for t in techs}),
            "core_features": features or ["basic functionality"],
            "constraints": [],
            "estimated_complexity": "simple" if len(message) < 100 else "medium",
        }
        return result
