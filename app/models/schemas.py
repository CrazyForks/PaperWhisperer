"""
Pydantic 数据模型定义
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class LLMProvider(str, Enum):
    """LLM 提供商"""
    QWEN = "qwen"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"


# ========== 论文相关模型 ==========

class PaperMetadata(BaseModel):
    """论文元数据"""
    paper_id: str
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    abstract: Optional[str] = None
    keywords: Optional[List[str]] = None
    publication_date: Optional[str] = None
    source: Optional[str] = None  # PDF file or URL
    created_at: datetime = Field(default_factory=datetime.now)


class PaperSection(BaseModel):
    """论文章节"""
    section_id: str
    title: str
    content: str
    level: int = 1  # 章节层级
    order: int  # 章节顺序


class PaperStructure(BaseModel):
    """论文结构"""
    paper_id: str
    metadata: PaperMetadata
    sections: List[PaperSection]
    full_content: str  # Markdown 格式的完整内容


# ========== 上传相关模型 ==========

class UploadResponse(BaseModel):
    """上传响应"""
    task_id: str
    status: TaskStatus
    message: str


class ParseStatusResponse(BaseModel):
    """解析状态响应"""
    task_id: str
    status: TaskStatus
    progress: Optional[int] = None  # 0-100
    paper_id: Optional[str] = None
    metadata: Optional[PaperMetadata] = None
    error: Optional[str] = None


# ========== 翻译相关模型 ==========

class TranslationRequest(BaseModel):
    """翻译请求"""
    paper_id: str
    source_lang: str = "en"
    target_lang: str = "zh"
    provider: Optional[LLMProvider] = None


class TranslationSegment(BaseModel):
    """翻译片段"""
    original: str
    translated: str
    section_title: Optional[str] = None


class TranslationResult(BaseModel):
    """翻译结果"""
    paper_id: str
    segments: List[TranslationSegment]
    status: TaskStatus
    created_at: datetime = Field(default_factory=datetime.now)


# ========== 摘要相关模型 ==========

class SummaryRequest(BaseModel):
    """摘要请求"""
    paper_id: str
    summary_type: str = "comprehensive"  # comprehensive, brief, technical
    provider: Optional[LLMProvider] = None


class SectionSummary(BaseModel):
    """章节摘要"""
    section_title: str
    summary: str


class PaperSummary(BaseModel):
    """论文摘要"""
    paper_id: str
    overall_summary: str
    key_points: List[str]
    methodology: Optional[str] = None
    contributions: Optional[str] = None
    section_summaries: List[SectionSummary]
    created_at: datetime = Field(default_factory=datetime.now)


# ========== 对话相关模型 ==========

class ChatMessage(BaseModel):
    """聊天消息"""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ChatRequest(BaseModel):
    """对话请求"""
    paper_id: Optional[str] = None  # 可选，因为已通过 URL 路径传递
    message: str
    session_id: Optional[str] = None
    provider: Optional[LLMProvider] = None
    stream: bool = False


class ChatResponse(BaseModel):
    """对话响应"""
    session_id: str
    message: ChatMessage
    sources: Optional[List[Dict[str, Any]]] = None  # 引用来源
    

class ChatHistory(BaseModel):
    """对话历史"""
    session_id: str
    paper_id: str
    messages: List[ChatMessage]
    created_at: datetime = Field(default_factory=datetime.now)


# ========== 向量化相关模型 ==========

class TextChunk(BaseModel):
    """文本块"""
    chunk_id: str
    paper_id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    

class EmbeddingResult(BaseModel):
    """Embedding 结果"""
    chunk_id: str
    embedding: List[float]
    dimension: int


# ========== Agent 相关模型 ==========

class IntentCategory(str, Enum):
    """意图类别"""
    CONTRIBUTION = "contribution"
    METHOD = "method"
    EXPERIMENT = "experiment"
    COMPARISON = "comparison"
    MOTIVATION = "motivation"
    IMPLEMENTATION = "implementation"
    GENERAL = "general"  # 通用问题


class IntentAnalysisResult(BaseModel):
    """意图分析结果"""
    category: IntentCategory
    target_sections: List[str] = Field(default_factory=list, description="目标章节列表")
    keywords: List[str] = Field(default_factory=list, description="检索关键词")
    reasoning: str = Field(default="", description="分析推理过程")


class CompletenessEvaluation(BaseModel):
    """信息完备性评估结果"""
    is_sufficient: bool = Field(description="信息是否足够回答问题")
    missing_info: Optional[str] = Field(default=None, description="缺失信息描述")
    suggested_keywords: List[str] = Field(default_factory=list, description="建议补充检索的关键词")
    reasoning: str = Field(default="", description="评估推理过程")


class AgentStreamEvent(BaseModel):
    """Agent 流式事件"""
    type: str = Field(description="事件类型: thinking/retrieval/evaluation/content/sources/done/error")
    content: Any = Field(description="事件内容")


class AgentChatRequest(BaseModel):
    """Agent 对话请求"""
    message: str
    session_id: Optional[str] = None
    provider: Optional[LLMProvider] = None

