"""Task Filter module using Qwen3-0.6B for task classification and semantic deduplication."""

import hashlib
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..utils import get_logger
from ..exceptions import WeChatAutomationError

logger = get_logger("filter")


class FilterError(WeChatAutomationError):
    """Base exception for filter errors."""
    pass


class LLMFilterError(FilterError):
    """Raised when LLM filtering fails."""
    pass


@dataclass
class FilterResult:
    """Result of task filtering."""
    is_task: bool
    confidence: float
    reason: Optional[str] = None
    category: Optional[str] = None
    keywords: List[str] = field(default_factory=list)


@dataclass
class DeduplicationResult:
    """Result of deduplication check."""
    is_duplicate: bool
    similar_message_id: Optional[str] = None
    similarity_score: float = 0.0


@dataclass
class FilterConfig:
    """Configuration for task filter."""
    model_name: str = "Qwen/Qwen3-0.6B"
    device: str = "auto"  # auto, cpu, cuda
    task_threshold: float = 0.5
    dedup_threshold: float = 0.85
    max_history: int = 100
    cache_embeddings: bool = True
    timeout: float = 30.0


class TaskFilter:
    """
    Task Filter using Qwen3-0.6B.
    
    Features:
    - Task classification using LLM
    - Semantic deduplication using embeddings
    - Configurable thresholds
    - Caching for performance
    """
    
    TASK_CLASSIFICATION_PROMPT = """你是一个消息分类器。判断以下消息是否是一个需要执行的任务。

消息："{message}"

任务定义：需要有人去完成的具体工作，如开发需求、bug修复、功能实现、配置修改等。

请回答：
1. 是否为任务：是/否
2. 置信度：0.0-1.0
3. 任务类型：开发/修复/配置/其他/无
4. 简短理由

请用以下格式回答：
是/否|置信度|类型|理由"""

    def __init__(self, config: Optional[FilterConfig] = None):
        self.config = config or FilterConfig()
        self._model = None
        self._tokenizer = None
        self._embedding_model = None
        self._message_history: deque = deque(maxlen=self.config.max_history)
        self._embedding_cache: Dict[str, List[float]] = {}
        self._initialized = False
        
        self._stats = {
            "total_messages": 0,
            "tasks_detected": 0,
            "duplicates_found": 0,
            "llm_calls": 0,
            "cache_hits": 0,
        }
    
    def _init_model(self) -> None:
        """Initialize the LLM model."""
        if self._initialized:
            return
        
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            
            logger.info(f"Loading model: {self.config.model_name}")
            
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                trust_remote_code=True,
            )
            
            self._model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                torch_dtype=torch.float16 if self.config.device == "cuda" else torch.float32,
                device_map=self.config.device,
                trust_remote_code=True,
            )
            
            self._model.eval()
            
            logger.info("Model loaded successfully")
            self._initialized = True
            
        except ImportError as e:
            logger.warning(f"Transformers not available: {e}")
            logger.info("Falling back to rule-based classification")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise LLMFilterError(f"Failed to initialize model: {e}")
    
    def _init_embedding_model(self) -> None:
        """Initialize the embedding model for deduplication."""
        if self._embedding_model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            
            logger.info("Loading embedding model")
            self._embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            logger.info("Embedding model loaded")
            
        except ImportError:
            logger.warning("sentence-transformers not available, using hash-based dedup")
        except Exception as e:
            logger.warning(f"Failed to load embedding model: {e}")
    
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM with a prompt."""
        self._init_model()
        
        if self._model is None or self._tokenizer is None:
            return self._fallback_classification(prompt)
        
        try:
            import torch
            
            inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
            
            if self.config.device == "cuda":
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=100,
                    temperature=0.1,
                    do_sample=False,
                    pad_token_id=self._tokenizer.eos_token_id,
                )
            
            response = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
            response = response[len(prompt):].strip()
            
            self._stats["llm_calls"] += 1
            
            return response
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return self._fallback_classification(prompt)
    
    def _fallback_classification(self, prompt: str) -> str:
        """Fallback classification using rules."""
        task_keywords = ["需求", "开发", "修复", "bug", "功能", "实现", "配置", "部署", "测试", "任务"]
        
        message = prompt.split('消息："')[1].split('"')[0] if '消息："' in prompt else ""
        message_lower = message.lower()
        
        matched = [kw for kw in task_keywords if kw in message_lower]
        
        if matched:
            return f"是|0.8|其他|匹配关键词: {', '.join(matched)}"
        else:
            return f"否|0.3|无|未匹配任务关键词"
    
    def classify(self, message: str) -> FilterResult:
        """
        Classify whether a message is a task.
        
        Args:
            message: The message content
            
        Returns:
            FilterResult with classification
        """
        self._stats["total_messages"] += 1
        
        prompt = self.TASK_CLASSIFICATION_PROMPT.format(message=message)
        response = self._call_llm(prompt)
        
        try:
            parts = response.split("|")
            is_task_str = parts[0].strip() if len(parts) > 0 else "否"
            confidence_str = parts[1].strip() if len(parts) > 1 else "0.5"
            category = parts[2].strip() if len(parts) > 2 else "其他"
            reason = parts[3].strip() if len(parts) > 3 else None
            
            is_task = is_task_str == "是"
            confidence = float(confidence_str)
            
            if confidence >= self.config.task_threshold and is_task:
                self._stats["tasks_detected"] += 1
            
            return FilterResult(
                is_task=is_task and confidence >= self.config.task_threshold,
                confidence=confidence,
                reason=reason,
                category=category,
                keywords=[],
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {response}, error: {e}")
            return FilterResult(
                is_task=False,
                confidence=0.0,
                reason=f"Parse error: {e}",
            )
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text."""
        self._init_embedding_model()
        
        if self._embedding_model is None:
            return None
        
        cache_key = hashlib.md5(text.encode()).hexdigest()
        
        if self.config.cache_embeddings and cache_key in self._embedding_cache:
            self._stats["cache_hits"] += 1
            return self._embedding_cache[cache_key]
        
        try:
            embedding = self._embedding_model.encode(text, convert_to_numpy=True)
            embedding_list = embedding.tolist()
            
            if self.config.cache_embeddings:
                self._embedding_cache[cache_key] = embedding_list
            
            return embedding_list
            
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return None
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def check_duplicate(
        self,
        message: str,
        message_id: str,
    ) -> DeduplicationResult:
        """
        Check if a message is a duplicate.
        
        Args:
            message: The message content
            message_id: Unique message identifier
            
        Returns:
            DeduplicationResult
        """
        embedding = self.get_embedding(message)
        
        if embedding is None:
            text_hash = hashlib.md5(message.encode()).hexdigest()
            for hist_id, hist_hash, _ in self._message_history:
                if hist_hash == text_hash:
                    self._stats["duplicates_found"] += 1
                    return DeduplicationResult(
                        is_duplicate=True,
                        similar_message_id=hist_id,
                        similarity_score=1.0,
                    )
            
            self._message_history.append((message_id, text_hash, None))
            return DeduplicationResult(is_duplicate=False)
        
        for hist_id, _, hist_embedding in self._message_history:
            if hist_embedding is None:
                continue
            
            similarity = self.cosine_similarity(embedding, hist_embedding)
            
            if similarity >= self.config.dedup_threshold:
                self._stats["duplicates_found"] += 1
                return DeduplicationResult(
                    is_duplicate=True,
                    similar_message_id=hist_id,
                    similarity_score=similarity,
                )
        
        text_hash = hashlib.md5(message.encode()).hexdigest()
        self._message_history.append((message_id, text_hash, embedding))
        
        return DeduplicationResult(is_duplicate=False)
    
    def filter(
        self,
        message: str,
        message_id: str,
        skip_dedup: bool = False,
    ) -> Tuple[FilterResult, DeduplicationResult]:
        """
        Filter a message: classify and check for duplicates.
        
        Args:
            message: The message content
            message_id: Unique message identifier
            skip_dedup: Skip deduplication check
            
        Returns:
            Tuple of (FilterResult, DeduplicationResult)
        """
        dedup_result = DeduplicationResult(is_duplicate=False)
        
        if not skip_dedup:
            dedup_result = self.check_duplicate(message, message_id)
        
        if dedup_result.is_duplicate:
            filter_result = FilterResult(
                is_task=False,
                confidence=0.0,
                reason="Duplicate message",
            )
        else:
            filter_result = self.classify(message)
        
        return filter_result, dedup_result
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get filter statistics."""
        return {
            **self._stats,
            "history_size": len(self._message_history),
            "cache_size": len(self._embedding_cache),
        }
    
    def clear_history(self) -> None:
        """Clear message history."""
        self._message_history.clear()
        self._embedding_cache.clear()
        logger.info("Filter history cleared")
