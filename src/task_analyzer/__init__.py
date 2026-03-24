"""Task analyzer for extracting requirements from WeChat messages."""

import json
import re
from typing import List, Optional
from ..llm_router.providers import Message
from ..llm_router.router import LLMRouter
from ..feishu_recorder.models import TaskRecord
from ..utils import get_logger

logger = get_logger("task_analyzer")


# Prompt template for task analysis
TASK_ANALYSIS_PROMPT = """你是一个需求分析助手。请分析以下消息，提取关键信息。

原始消息: {message}

请以JSON格式输出:
{{
  "summary": "简短的需求摘要 (50字内)",
  "tech_stack": ["技术栈列表"],
  "core_features": ["核心功能1", "核心功能2"],
  "constraints": ["约束条件"],
  "estimated_complexity": "simple/medium/complex"
}}
"""

DEFAULT_RESPONSE = {
    "summary": "待分析任务",
    "tech_stack": [],
    "core_features": [],
    "constraints": [],
    "estimated_complexity": "medium"
}


class TaskAnalyzer:
    """
    Analyzer that uses LLM to extract structured task information from messages.
    """
    
    def __init__(self, llm_router: Optional[LLMRouter] = None):
        """
        Initialize task analyzer.
        
        Args:
            llm_router: LLM router instance (optional, will create if None)
        """
        self.llm_router = llm_router or LLMRouter()
    
    async def analyze(self, message: str) -> TaskRecord:
        """
        Analyze a message and extract task information.
        
        Args:
            message: Raw message text
            
        Returns:
            TaskRecord with extracted information
        """
        try:
            # Format prompt
            prompt = TASK_ANALYSIS_PROMPT.format(message=message)
            
            # Call LLM
            response = await self.llm_router.complete(prompt)
            
            # Parse JSON response
            return self._parse_response(response.content, message)
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return self._create_default_record(message)
        except Exception as e:
            logger.error(f"Task analysis failed: {e}")
            return self._create_default_record(message)
    
    def _parse_response(self, content: str, raw_message: str) -> TaskRecord:
        """Parse LLM JSON response into TaskRecord."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(content)
            
            return TaskRecord(
                task_id=f"task_{hash(raw_message) % 1000000}",
                raw_message=raw_message,
                summary=data.get("summary", DEFAULT_RESPONSE["summary"]),
                tech_stack=data.get("tech_stack", DEFAULT_RESPONSE["tech_stack"]),
                core_features=data.get("core_features", DEFAULT_RESPONSE["core_features"]),
                constraints=data.get("constraints", DEFAULT_RESPONSE["constraints"]),
                estimated_complexity=data.get("estimated_complexity", "medium"),
            )
        except Exception:
            return self._create_default_record(raw_message)
    
    def _create_default_record(self, raw_message: str) -> TaskRecord:
        """Create a default record when parsing fails."""
        return TaskRecord(
            task_id=f"task_{hash(raw_message) % 1000000}",
            raw_message=raw_message,
            summary="待分析任务",
            tech_stack=[],
            core_features=[],
            constraints=[],
            estimated_complexity="medium",
        )
    
    async def generate_instruction(self, record: TaskRecord) -> str:
        """
        Generate an OpenCode instruction from a TaskRecord.
        
        Args:
            record: TaskRecord to convert
            
        Returns:
            Natural language instruction for OpenCode
        """
        prompt = f"""根据以下任务信息，生成一个清晰的OpenCode执行指令:

任务摘要: {record.summary}
技术栈: {', '.join(record.tech_stack) if record.tech_stack else '未指定'}
核心功能:
{chr(10).join(f'- {f}' for f in record.core_features) if record.core_features else '- 未指定'}

请生成一个简洁的指令，直接告诉OpenCode要做什么。
"""
        
        try:
            response = await self.llm_router.complete(prompt)
            return response.content.strip()
        except Exception as e:
            logger.error(f"Failed to generate instruction: {e}")
            return f"Create code for: {record.summary}"
