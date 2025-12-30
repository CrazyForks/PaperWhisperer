"""
Agent 服务
实现基于论文的智能对话 Agent，包含意图识别、信息完备性评估和检索编排
"""
import json
import re
from typing import List, Dict, Any, Optional, AsyncIterator

from app.models.schemas import (
    ChatMessage,
    ChatHistory,
    IntentCategory,
    IntentAnalysisResult,
    CompletenessEvaluation,
    AgentStreamEvent
)
from app.services.llm_factory import llm_factory
from app.services.vectorization_service import vectorization_service
from app.utils.logger import log
from app.utils.file_manager import FileManager
from app.config import settings
from datetime import datetime
import uuid


class IntentAnalyzer:
    """意图分析器 - 分析用户问题的意图类别、目标章节和检索关键词"""
    
    INTENT_ANALYSIS_PROMPT = """你是一个专业的学术论文分析助手。请分析用户的问题意图。

## 论文章节结构
{section_titles}

## 对话历史
{conversation_history}

## 当前用户问题
{question}

## 任务
请分析用户问题的意图，并返回以下 JSON 格式结果：

```json
{{
    "category": "<意图类别>",
    "target_sections": ["<目标章节1>", "<目标章节2>"],
    "keywords": ["<关键词1>", "<关键词2>", "<关键词3>"],
    "reasoning": "<分析推理过程>"
}}
```

## 意图类别说明
- contribution: 询问论文的主要贡献、创新点、novelty
- method: 询问研究方法、技术方案、算法设计
- experiment: 询问实验设置、实验结果、数据集、评估指标
- comparison: 询问与其他方法的对比、baseline、性能差异
- motivation: 询问研究动机、问题背景、为什么要做这个研究
- implementation: 询问具体实现细节、代码、超参数
- general: 通用问题，如摘要、概述、其他

## 要求
1. target_sections 应该从论文章节结构中选择最相关的1-3个章节
2. keywords 应该提取3-5个用于检索的关键词或关键短语
3. reasoning 简要说明分析过程

请直接返回 JSON，不要有任何前缀或后缀文字。"""

    @staticmethod
    async def analyze(
        question: str,
        section_titles: List[str],
        conversation_history: List[ChatMessage] = None,
        provider: Optional[str] = None
    ) -> IntentAnalysisResult:
        """
        分析用户问题意图
        
        Args:
            question: 用户问题
            section_titles: 论文章节标题列表
            conversation_history: 对话历史
            provider: LLM 提供商
            
        Returns:
            IntentAnalysisResult 意图分析结果
        """
        # 格式化章节标题
        section_titles_str = "\n".join([f"- {title}" for title in section_titles]) if section_titles else "（未提供章节结构）"
        
        # 格式化对话历史
        history_str = "（无历史对话）"
        if conversation_history:
            history_parts = []
            for msg in conversation_history[-6:]:  # 最近3轮对话
                role = "用户" if msg.role == "user" else "助手"
                history_parts.append(f"{role}: {msg.content[:200]}...")
            history_str = "\n".join(history_parts)
        
        prompt = IntentAnalyzer.INTENT_ANALYSIS_PROMPT.format(
            section_titles=section_titles_str,
            conversation_history=history_str,
            question=question
        )
        
        messages = [
            {"role": "system", "content": "你是专业的学术论文分析专家。请始终返回有效的 JSON 格式。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await llm_factory.chat(
                messages=messages,
                provider=provider,
                temperature=settings.agent_intent_temperature,
                max_tokens=800,
                stream=False
            )
            
            # 清理并解析结果
            result = result.strip()
            if result.startswith("```"):
                lines = result.split('\n')
                result = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
                result = result.strip()
            
            parsed = json.loads(result)
            
            # 转换 category 字符串为枚举
            category_str = parsed.get("category", "general").lower()
            try:
                category = IntentCategory(category_str)
            except ValueError:
                category = IntentCategory.GENERAL
            
            return IntentAnalysisResult(
                category=category,
                target_sections=parsed.get("target_sections", []),
                keywords=parsed.get("keywords", []),
                reasoning=parsed.get("reasoning", "")
            )
            
        except json.JSONDecodeError as e:
            log.warning(f"意图分析结果解析失败: {e}, 原始结果: {result[:200]}")
            # 返回默认结果
            return IntentAnalysisResult(
                category=IntentCategory.GENERAL,
                target_sections=[],
                keywords=[question[:50]],  # 使用问题本身作为关键词
                reasoning="解析失败，使用默认设置"
            )
        except Exception as e:
            log.error(f"意图分析失败: {e}")
            raise


class CompletenessEvaluator:
    """信息完备性评估器 - 评估检索到的内容是否足够回答用户问题"""
    
    EVALUATION_PROMPT = """你是一个专业的信息完备性评估专家。请评估当前检索到的信息是否足够回答用户的问题。

## 用户原始问题
{question}

## 检索到的相关内容
{retrieved_content}

## 任务
请评估上述检索内容是否足够回答用户的问题，并返回以下 JSON 格式结果：

```json
{{
    "is_sufficient": true/false,
    "missing_info": "<如果不足够，说明缺少什么信息>",
    "suggested_keywords": ["<建议补充检索的关键词1>", "<关键词2>"],
    "reasoning": "<评估推理过程>"
}}
```

## 评估标准
1. 信息是否直接回答了用户的核心问题
2. 是否有足够的细节和上下文
3. 是否需要补充其他章节的内容

请直接返回 JSON，不要有任何前缀或后缀文字。"""

    @staticmethod
    async def evaluate(
        question: str,
        retrieved_content: str,
        provider: Optional[str] = None
    ) -> CompletenessEvaluation:
        """
        评估信息完备性
        
        Args:
            question: 用户问题
            retrieved_content: 检索到的内容
            provider: LLM 提供商
            
        Returns:
            CompletenessEvaluation 评估结果
        """
        prompt = CompletenessEvaluator.EVALUATION_PROMPT.format(
            question=question,
            retrieved_content=retrieved_content[:4000]  # 限制长度
        )
        
        messages = [
            {"role": "system", "content": "你是专业的信息完备性评估专家。请始终返回有效的 JSON 格式。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await llm_factory.chat(
                messages=messages,
                provider=provider,
                temperature=settings.agent_evaluation_temperature,
                max_tokens=500,
                stream=False
            )
            
            # 清理并解析结果
            result = result.strip()
            if result.startswith("```"):
                lines = result.split('\n')
                result = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
                result = result.strip()
            
            parsed = json.loads(result)
            
            return CompletenessEvaluation(
                is_sufficient=parsed.get("is_sufficient", True),
                missing_info=parsed.get("missing_info"),
                suggested_keywords=parsed.get("suggested_keywords", []),
                reasoning=parsed.get("reasoning", "")
            )
            
        except json.JSONDecodeError as e:
            log.warning(f"完备性评估结果解析失败: {e}")
            # 默认认为信息足够，避免无限循环
            return CompletenessEvaluation(
                is_sufficient=True,
                missing_info=None,
                suggested_keywords=[],
                reasoning="解析失败，默认信息充足"
            )
        except Exception as e:
            log.error(f"完备性评估失败: {e}")
            raise


class AgentOrchestrator:
    """Agent 编排器 - 协调意图识别、检索和完备性评估的完整流程"""
    
    ANSWER_PROMPT = """你是一个专业的学术论文助手。请基于提供的论文内容回答用户的问题。

## 论文相关片段
{context}

## 用户问题
{question}

## 回答要求
1. 基于提供的论文片段回答问题，不要编造信息
2. 如果论文片段中没有相关信息，请明确说明
3. 使用清晰、准确的学术语言
4. 如果问题涉及多个方面，请分点回答
5. 必要时可以引用论文原文

请给出详细、准确的回答："""

    def __init__(self):
        self.max_retrieval_rounds = settings.agent_max_retrieval_rounds
        # 会话存储
        self.sessions: Dict[str, ChatHistory] = {}
    
    def create_session(self, paper_id: str) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = ChatHistory(
            session_id=session_id,
            paper_id=paper_id,
            messages=[],
            created_at=datetime.now()
        )
        log.info(f"Agent 创建会话: {session_id}, 论文: {paper_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[ChatHistory]:
        """获取会话"""
        return self.sessions.get(session_id)
    
    def _format_context(self, search_results: List[Dict[str, Any]]) -> str:
        """格式化检索结果为上下文"""
        context_parts = []
        for i, result in enumerate(search_results, 1):
            text = result["text"]
            section = result["metadata"].get("section_title", "未知章节")
            score = result["score"]
            context_parts.append(f"[片段 {i}] (章节: {section}, 相关度: {score:.3f})\n{text}\n")
        return "\n---\n\n".join(context_parts)
    
    def _deduplicate_results(self, all_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重检索结果"""
        seen_chunks = set()
        deduplicated = []
        for result in all_results:
            chunk_id = result.get("chunk_id")
            if chunk_id and chunk_id not in seen_chunks:
                seen_chunks.add(chunk_id)
                deduplicated.append(result)
        return deduplicated
    
    async def _get_section_titles(self, paper_id: str) -> List[str]:
        """从论文 JSON 文件中直接读取章节标题列表"""
        try:
            # 直接从保存的 JSON 文件读取章节标题，效率更高
            paper_data = await FileManager.load_parsed_content(paper_id)
            if paper_data and "sections" in paper_data:
                sections = paper_data["sections"]
                return [section.get("title", "") for section in sections if section.get("title")]
        except Exception as e:
            log.warning(f"获取章节标题失败: {e}")
        return []
    
    async def chat_stream(
        self,
        paper_id: str,
        question: str,
        session_id: Optional[str] = None,
        provider: Optional[str] = None
    ) -> AsyncIterator[AgentStreamEvent]:
        """
        Agent 流式对话
        
        Args:
            paper_id: 论文ID
            question: 用户问题
            session_id: 会话ID
            provider: LLM 提供商
            
        Yields:
            AgentStreamEvent 流式事件
        """
        # 创建或获取会话
        if not session_id:
            session_id = self.create_session(paper_id)
        
        session = self.get_session(session_id)
        if not session or session.paper_id != paper_id:
            yield AgentStreamEvent(type="error", content="会话无效或论文不匹配")
            return
        
        try:
            # === 第1步：意图识别 ===
            yield AgentStreamEvent(type="thinking", content="正在分析问题意图...")
            
            # 获取章节标题列表
            section_titles = await self._get_section_titles(paper_id)
            
            intent_result = await IntentAnalyzer.analyze(
                question=question,
                section_titles=section_titles,
                conversation_history=session.messages,
                provider=provider
            )
            
            yield AgentStreamEvent(
                type="thinking",
                content=f"意图识别完成:\n- 类别: {intent_result.category.value}\n- 目标章节: {', '.join(intent_result.target_sections) or '全文'}\n- 关键词: {', '.join(intent_result.keywords)}\n- 推理: {intent_result.reasoning}"
            )
            
            # === 第2步：RAG 检索循环 ===
            all_results = []
            current_round = 0
            is_sufficient = False
            
            while current_round < self.max_retrieval_rounds and not is_sufficient:
                current_round += 1
                
                # 确定本轮检索关键词
                if current_round == 1:
                    search_keywords = intent_result.keywords
                else:
                    # 使用上一轮评估建议的关键词
                    search_keywords = evaluation_result.suggested_keywords or [question]
                
                yield AgentStreamEvent(
                    type="retrieval",
                    content=f"第 {current_round} 轮检索 (关键词: {', '.join(search_keywords)})"
                )
                
                # 执行多关键词检索
                for keyword in search_keywords[:3]:  # 限制关键词数量
                    results = await vectorization_service.search_similar_chunks(
                        query_text=keyword,
                        paper_id=paper_id,
                        top_k=settings.top_k_retrieval
                    )
                    all_results.extend(results)
                
                # 去重
                all_results = self._deduplicate_results(all_results)
                
                yield AgentStreamEvent(
                    type="retrieval",
                    content=f"检索到 {len(all_results)} 个相关片段"
                )
                
                if not all_results:
                    yield AgentStreamEvent(
                        type="evaluation",
                        content="未检索到相关内容"
                    )
                    break
                
                # === 第3步：信息完备性评估 ===
                yield AgentStreamEvent(type="thinking", content="正在评估信息完备性...")
                
                context = self._format_context(all_results)
                evaluation_result = await CompletenessEvaluator.evaluate(
                    question=question,
                    retrieved_content=context,
                    provider=provider
                )
                
                is_sufficient = evaluation_result.is_sufficient
                
                if is_sufficient:
                    yield AgentStreamEvent(
                        type="evaluation",
                        content=f"信息评估: 信息充足，开始生成回答\n推理: {evaluation_result.reasoning}"
                    )
                else:
                    if current_round < self.max_retrieval_rounds:
                        yield AgentStreamEvent(
                            type="evaluation",
                            content=f"信息评估: 需要补充信息\n缺失: {evaluation_result.missing_info}\n建议关键词: {', '.join(evaluation_result.suggested_keywords)}"
                        )
                    else:
                        yield AgentStreamEvent(
                            type="evaluation",
                            content=f"信息评估: 已达最大检索轮次，基于现有信息回答\n缺失: {evaluation_result.missing_info}"
                        )
            
            # === 第4步：生成回答 ===
            if not all_results:
                answer = "抱歉，我在论文中没有找到与您问题相关的内容。您可以尝试换一个问法或问其他问题。"
                yield AgentStreamEvent(type="content", content=answer)
            else:
                context = self._format_context(all_results)
                prompt = self.ANSWER_PROMPT.format(
                    context=context,
                    question=question
                )
                
                messages = [
                    {"role": "system", "content": "你是专业的学术论文助手。"},
                    {"role": "user", "content": prompt}
                ]
                
                # 添加历史对话
                if session.messages:
                    recent_history = session.messages[-6:]
                    history_messages = [{"role": msg.role, "content": msg.content} for msg in recent_history]
                    messages = messages[:1] + history_messages + messages[1:]
                
                # 流式生成回答
                response_chunks = []
                stream_generator = await llm_factory.chat(
                    messages=messages,
                    provider=provider,
                    temperature=0.7,
                    stream=True
                )
                
                async for chunk in stream_generator:
                    response_chunks.append(chunk)
                    yield AgentStreamEvent(type="content", content=chunk)
                
                answer = "".join(response_chunks)
            
            # === 第5步：返回来源并保存历史 ===
            yield AgentStreamEvent(
                type="sources",
                content=[{
                    "chunk_id": r.get("chunk_id"),
                    "section": r.get("metadata", {}).get("section_title", ""),
                    "score": r.get("score", 0),
                    "text_preview": r.get("text", "")[:100] + "..."
                } for r in all_results[:5]]
            )
            
            # 保存对话历史
            user_message = ChatMessage(role="user", content=question, timestamp=datetime.now())
            assistant_message = ChatMessage(role="assistant", content=answer, timestamp=datetime.now())
            session.messages.append(user_message)
            session.messages.append(assistant_message)
            
            # 限制历史长度
            if len(session.messages) > 20:
                session.messages = session.messages[-20:]
            
            yield AgentStreamEvent(type="done", content=True)
            
        except Exception as e:
            log.error(f"Agent 对话失败: {e}")
            yield AgentStreamEvent(type="error", content=str(e))
    
    def get_history(self, session_id: str) -> Optional[List[ChatMessage]]:
        """获取对话历史"""
        session = self.get_session(session_id)
        return session.messages if session else None
    
    def clear_session(self, session_id: str):
        """清除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            log.info(f"Agent 清除会话: {session_id}")


# 全局服务实例
agent_service = AgentOrchestrator()

