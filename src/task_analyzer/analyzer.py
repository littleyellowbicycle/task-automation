from __future__ import annotations

import json
import re
from typing import List, Dict, Any, Optional

from ..llm_router.router import LLMRouter, LLMResponse
from ..utils import get_logger

logger = get_logger("task_analyzer")


class TaskAnalyzer:
    """
    Task analyzer using LLM to extract structured information from task messages.

    Extracts:
    - summary: Brief description of the task
    - tech_stack: List of technologies mentioned or implied
    - core_features: Key functionality required
    - constraints: Any constraints or requirements
    - estimated_complexity: simple/medium/complex
    """

    ANALYSIS_PROMPT = """你是一个任务分析助手。从用户消息中提取结构化的任务信息。

消息："{message}"

请分析这个消息，提取以下信息：

1. summary: 任务的一句话摘要（不超过100字）
2. tech_stack: 涉及的技术栈列表（如 Python, JavaScript, React, PostgreSQL, Docker 等）
3. core_features: 核心功能点列表（如用户认证、API接口、数据库操作、前端渲染等）
4. constraints: 约束条件或特殊要求（如性能要求、安全要求、兼容性要求等）
5. estimated_complexity: 预估复杂度（simple/medium/complex）

请用 JSON 格式返回结果：
{{
    "summary": "...",
    "tech_stack": ["Python", "FastAPI"],
    "core_features": ["REST API", "用户认证"],
    "constraints": ["需要支持移动端"],
    "estimated_complexity": "medium"
}}

只返回 JSON，不要有其他内容。"""

    FALLBACK_RESULT = {
        "summary": "",
        "tech_stack": [],
        "core_features": [],
        "constraints": [],
        "estimated_complexity": "simple",
    }

    TECH_KEYWORDS = [
        "Python",
        "Java",
        "Go",
        "JavaScript",
        "TypeScript",
        "C++",
        "C#",
        "Rust",
        "Ruby",
        "PHP",
        "React",
        "Vue",
        "Angular",
        "Svelte",
        "Next.js",
        "Nuxt",
        "Django",
        "Flask",
        "FastAPI",
        "Spring",
        "Express",
        "Koa",
        "Node",
        "NestJS",
        "PostgreSQL",
        "MySQL",
        "MongoDB",
        "Redis",
        "Elasticsearch",
        "SQLite",
        "Docker",
        "Kubernetes",
        "AWS",
        "Azure",
        "GCP",
        "Terraform",
        "GraphQL",
        "REST",
        "gRPC",
        "WebSocket",
        "MQTT",
        "Git",
        "CI/CD",
        "Jenkins",
        "GitHub Actions",
        "GitLab CI",
        "Vue",
        "React",
        "Angular",
        "Flutter",
        "React Native",
        "Swift",
        "Kotlin",
    ]

    FEATURE_KEYWORDS = [
        "登录",
        "登录",
        "authentication",
        "login",
        "注册",
        "registration",
        "API",
        "接口",
        "crud",
        "增删改查",
        "数据库",
        "database",
        "db",
        "存储",
        "storage",
        "前端",
        "frontend",
        "后端",
        "backend",
        "全栈",
        "fullstack",
        "实时",
        "realtime",
        "websocket",
        "推送",
        "push",
        "搜索",
        "search",
        "分页",
        "pagination",
        "排序",
        "sort",
        "权限",
        "permission",
        "角色",
        "role",
        " RBAC",
        "文件上传",
        "upload",
        "下载",
        "download",
        "导出",
        "export",
        "导入",
        "import",
        "图表",
        "chart",
        "可视化",
        "visualization",
        "缓存",
        "cache",
        "队列",
        "queue",
        "消息",
        "message",
        "通知",
        "notification",
        "邮件",
        "email",
        "短信",
        "sms",
        "支付",
        "payment",
        "订单",
        "order",
        "评论",
        "comment",
        "点赞",
        "like",
    ]

    def __init__(self, llm_router: Optional[LLMRouter] = None):
        self._llm_router = llm_router

    @property
    def llm_router(self) -> LLMRouter:
        if self._llm_router is None:
            self._llm_router = LLMRouter.create_default()
        return self._llm_router

    def _extract_tech_with_fallback(self, message: str) -> List[str]:
        techs = []
        lower = message.lower()
        for tech in self.TECH_KEYWORDS:
            if tech.lower() in lower:
                techs.append(tech)
        return list(dict.fromkeys(techs))

    def _extract_features_with_fallback(self, message: str) -> List[str]:
        features = []
        lower = message.lower()
        for feat in self.FEATURE_KEYWORDS:
            if feat.lower() in lower:
                features.append(feat if len(feat) > 2 else feat.upper())
        return features if features else ["基础功能"]

    def _estimate_complexity_with_fallback(
        self, message: str, techs: List[str], features: List[str]
    ) -> str:
        length = len(message)
        complexity_score = 0

        if length > 200:
            complexity_score += 1
        if length > 400:
            complexity_score += 1
        if len(techs) > 2:
            complexity_score += 1
        if len(features) > 3:
            complexity_score += 1
        if any(
            kw in message.lower()
            for kw in ["复杂", "分布式", "微服务", "高并发", "complex", "distributed"]
        ):
            complexity_score += 2

        if complexity_score <= 1:
            return "simple"
        elif complexity_score <= 3:
            return "medium"
        else:
            return "complex"

    def _parse_llm_response(self, content: str) -> Optional[Dict[str, Any]]:
        try:
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)

            if not isinstance(result, dict):
                return None

            return {
                "summary": str(result.get("summary", "")),
                "tech_stack": result.get("tech_stack", []),
                "core_features": result.get("core_features", []),
                "constraints": result.get("constraints", []),
                "estimated_complexity": result.get("estimated_complexity", "simple"),
            }
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            try:
                summary_match = re.search(r'"summary"\s*:\s*"([^"]*)"', content)
                if summary_match:
                    return {"summary": summary_match.group(1)}
            except Exception:
                pass
            return None

    async def analyze_async(self, message: str) -> Dict[str, Any]:
        if not message:
            return self.FALLBACK_RESULT.copy()

        prompt = self.ANALYSIS_PROMPT.format(message=message)

        try:
            response = await self.llm_router.route_task(prompt, complexity="simple")
            if response.content and response.content != "no-provider-available":
                parsed = self._parse_llm_response(response.content)
                if parsed:
                    logger.info(
                        f"Task analyzed by LLM ({response.provider}): {parsed.get('summary', '')[:50]}"
                    )
                    return parsed
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}, falling back to heuristics")

        return self._fallback_analyze(message)

    def _fallback_analyze(self, message: str) -> Dict[str, Any]:
        techs = self._extract_tech_with_fallback(message)
        features = self._extract_features_with_fallback(message)
        complexity = self._estimate_complexity_with_fallback(message, techs, features)
        summary = message[:250] if len(message) > 250 else message

        return {
            "summary": summary,
            "tech_stack": techs,
            "core_features": features,
            "constraints": [],
            "estimated_complexity": complexity,
        }

    def analyze(self, message: str) -> Dict[str, Any]:
        """
        Synchronous analyze - for backward compatibility.
        Note: Prefer analyze_async for proper async behavior.
        """
        if not message:
            return self.FALLBACK_RESULT.copy()

        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = loop.create_task(self.analyze_async(message))
                return {
                    "summary": message[:250] if len(message) > 250 else message,
                    "tech_stack": self._extract_tech_with_fallback(message),
                    "core_features": self._extract_features_with_fallback(message),
                    "constraints": [],
                    "estimated_complexity": self._estimate_complexity_with_fallback(
                        message,
                        self._extract_tech_with_fallback(message),
                        self._extract_features_with_fallback(message),
                    ),
                }
            else:
                return loop.run_until_complete(self.analyze_async(message))
        except RuntimeError:
            return {
                "summary": message[:250] if len(message) > 250 else message,
                "tech_stack": self._extract_tech_with_fallback(message),
                "core_features": self._extract_features_with_fallback(message),
                "constraints": [],
                "estimated_complexity": self._estimate_complexity_with_fallback(
                    message,
                    self._extract_tech_with_fallback(message),
                    self._extract_features_with_fallback(message),
                ),
            }
