"""Qwen3 重排序模块（v9.0 Task 2.4）

基于 Qwen3-reranker-0.6B 的交叉编码器重排序。

该模型本质是 Qwen3ForCausalLM，遵循官方 Qwen3-Reranker 推理方式：
    1. 构造 yes/no 判别 prompt
    2. 取最后位置的 logits 中 "yes"/"no" 两个 token 的分数
    3. softmax 归一化，取 P(yes) 作为相关性分数

注意：不要使用 AutoModelForSequenceClassification，其分类头是随机初始化的。

典型用法：
    reranker = Qwen3Reranker()
    results = reranker.rerank(query, documents, top_k=5)
"""
from __future__ import annotations

import os
import threading
from typing import List, Optional

import numpy as np

try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)


# 项目根目录
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# 默认 instruction（学术检索场景）
DEFAULT_INSTRUCTION = (
    "Given a Chinese/English academic query, retrieve relevant thesis titles "
    "and abstracts that address the query's research topic."
)

# yes/no prompt 模板（官方 Qwen3-Reranker）
_PROMPT_TEMPLATE = (
    "<|im_start|>system>Judge whether the Document meets the requirements "
    'based on the Query and the Instruct provided. Note that the answer can '
    'only be "yes" or "no".<|im_end|>\n'
    "<|im_start|>user>\n"
    "<Instruct>: {instruction}\n"
    "<Query>: {query}\n"
    "<Document>: {document}<|im_end|>\n"
    "<|im_start|>assistant>\n"
    "<think>\n\n</think>\n\n"
)


class Qwen3Reranker:
    """基于 Qwen3-reranker-0.6B 的重排序器。

    使用 AutoModelForCausalLM + AutoTokenizer，按官方 yes/no 评分方式计算相关性。
    模型在首次 rerank 调用时才加载（延迟加载）。
    """

    def __init__(
        self,
        model_path: str = "Qwen3-reranker-0.6B",
        device: str = "auto",
        max_length: int = 8192,
        batch_size: int = 8,
    ):
        """初始化重排序器。

        Args:
            model_path: 模型路径（相对项目根或绝对路径）。
            device: 设备，"auto" 时自动检测。
            max_length: 单条输入最大 token 长度。
            batch_size: 批处理大小。
        """
        self.model_path = model_path
        self.device = device
        self.max_length = int(max_length)
        self.batch_size = int(batch_size)
        self._model = None
        self._tokenizer = None
        self._yes_no_ids: Optional[List[int]] = None
        self._lock = threading.Lock()
        self._loaded = False
        self._load_error: Optional[str] = None

    def _resolve_model_path(self) -> str:
        """解析模型路径。"""
        if os.path.isabs(self.model_path) and os.path.exists(self.model_path):
            return self.model_path
        candidate = os.path.join(_PROJECT_ROOT, self.model_path)
        if os.path.exists(candidate):
            return candidate
        return self.model_path

    def _resolve_device(self) -> str:
        """解析实际设备。"""
        if self.device == "auto":
            try:
                import torch

                if torch.cuda.is_available():
                    return "cuda"
            except Exception:
                pass
            return "cpu"
        return self.device

    def _ensure_loaded(self) -> bool:
        """延迟加载模型与 tokenizer，并缓存 yes/no token id。"""
        if self._loaded:
            return self._model is not None and self._tokenizer is not None
        with self._lock:
            if self._loaded:
                return self._model is not None and self._tokenizer is not None
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer

                resolved_path = self._resolve_model_path()
                device = self._resolve_device()
                _logger.info(
                    "加载 Qwen3 重排序模型: path=%s, device=%s",
                    resolved_path,
                    device,
                )
                self._tokenizer = AutoTokenizer.from_pretrained(
                    resolved_path, trust_remote_code=True
                )
                # 不使用 device_map（需要 accelerate 包），改为加载后 .to(device)
                self._model = AutoModelForCausalLM.from_pretrained(
                    resolved_path,
                    torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
                    trust_remote_code=True,
                )
                self._model = self._model.to(device)
                self._model.eval()
                # 缓存 yes/no token id（单 token）
                yes_ids = self._tokenizer.encode("yes", add_special_tokens=False)
                no_ids = self._tokenizer.encode("no", add_special_tokens=False)
                if not yes_ids or not no_ids:
                    raise RuntimeError("无法编码 yes/no token")
                self._yes_no_ids = [yes_ids[0], no_ids[0]]
                self._loaded = True
                _logger.info(
                    "Qwen3 重排序模型加载成功, yes_id=%d, no_id=%d",
                    self._yes_no_ids[0],
                    self._yes_no_ids[1],
                )
                return True
            except Exception as e:
                self._load_error = str(e)
                _logger.error("Qwen3 重排序模型加载失败: %s", e, exc_info=True)
                self._loaded = True
                self._model = None
                self._tokenizer = None
                return False

    def _build_prompt(self, query: str, document: str, instruction: str) -> str:
        """构造 yes/no 判别 prompt。"""
        return _PROMPT_TEMPLATE.format(
            instruction=instruction, query=query, document=document
        )

    def _score_batch(
        self,
        prompts: List[str],
    ) -> List[float]:
        """对一批 prompt 计算 P(yes) 分数。"""
        import torch

        scores: List[float] = []
        if not prompts:
            return scores
        if self._model is None or self._tokenizer is None or not self._yes_no_ids:
            return [0.0] * len(prompts)
        yes_id, no_id = self._yes_no_ids
        device = next(self._model.parameters()).device
        for i in range(0, len(prompts), self.batch_size):
            batch = prompts[i : i + self.batch_size]
            try:
                inputs = self._tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )
                input_ids = inputs["input_ids"].to(device)
                attention_mask = inputs["attention_mask"].to(device)
                with torch.no_grad():
                    outputs = self._model(
                        input_ids=input_ids, attention_mask=attention_mask
                    )
                # 取最后一个非 padding token 的 logits
                # shape: (batch, seq_len, vocab)
                logits = outputs.logits
                # 找到每行最后一个有效 token 位置
                # attention_mask: (batch, seq_len)
                lengths = attention_mask.sum(dim=1) - 1  # 末位索引
                # 收集每行末位 logits
                idx = lengths.view(-1, 1, 1).expand(-1, 1, logits.size(-1))
                last_logits = logits.gather(1, idx).squeeze(1)  # (batch, vocab)
                yes_logits = last_logits[:, yes_id]
                no_logits = last_logits[:, no_id]
                # 二元 softmax
                stacked = torch.stack([yes_logits, no_logits], dim=1)  # (batch, 2)
                probs = torch.softmax(stacked, dim=1)
                # 转 float32 再转 numpy（numpy 不支持 bfloat16）
                yes_probs = probs[:, 0].detach().float().cpu().numpy()
                for p in yes_probs:
                    scores.append(float(p))
            except Exception as e:
                _logger.error("Qwen3 rerank 批处理失败: %s", e, exc_info=True)
                scores.extend([0.0] * len(batch))
        return scores

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 10,
        instruction: str = DEFAULT_INSTRUCTION,
    ) -> List[dict]:
        """对文档列表重排序。

        Args:
            query: 查询字符串。
            documents: 候选文档文本列表。
            top_k: 返回结果数。
            instruction: 任务描述（影响判别标准）。

        Returns:
            结果列表，每项含 index/text/score 字段，按分数降序。
        """
        if not query or not documents or top_k <= 0:
            return []
        if not self._ensure_loaded():
            # 模型加载失败，按原始顺序返回零分
            return [
                {"index": i, "text": doc, "score": 0.0}
                for i, doc in enumerate(documents[:top_k])
            ]
        prompts = [self._build_prompt(query, doc, instruction) for doc in documents]
        scores = self._score_batch(prompts)
        results = [
            {"index": i, "text": doc, "score": float(s)}
            for i, (doc, s) in enumerate(zip(documents, scores))
        ]
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def is_loaded(self) -> bool:
        """模型是否已成功加载。"""
        return self._model is not None and self._tokenizer is not None

    def get_status(self) -> dict:
        """返回状态信息。"""
        return {
            "model_path": self.model_path,
            "device": self._resolve_device() if self.device == "auto" else self.device,
            "loaded": self._model is not None and self._tokenizer is not None,
            "load_error": self._load_error,
            "batch_size": self.batch_size,
            "max_length": self.max_length,
        }
