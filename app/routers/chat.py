"""
对话路由
处理基于论文的对话问答
支持普通对话和 Agent 智能对话

注意：路由定义顺序很重要！更具体的路由必须放在更通用的路由之前，
否则 FastAPI 可能无法正确匹配路由。
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import json

from app.models.schemas import ChatRequest, ChatResponse, ChatMessage, LLMProvider, AgentChatRequest
from app.services.rag_service import rag_service
from app.services.agent_service import agent_service
from app.utils.logger import log
from datetime import datetime

router = APIRouter()


# ========== 普通对话端点（具体路由在前，通用路由在后）==========

@router.post("/chat/new_session/{paper_id}")
async def create_new_session(paper_id: str):
    """
    创建新的对话会话
    """
    session_id = rag_service.create_session(paper_id)
    
    return {
        "session_id": session_id,
        "paper_id": paper_id,
        "message": "会话创建成功"
    }


@router.post("/chat/stream/{paper_id}")
async def chat_with_paper_stream(
    paper_id: str,
    request: ChatRequest
):
    """
    与论文对话（流式）
    """
    async def generate():
        """流式生成器"""
        try:
            async for chunk in rag_service.chat_stream(
                paper_id=paper_id,
                question=request.message,
                session_id=request.session_id,
                provider=request.provider.value if request.provider else None
            ):
                # 每个 chunk 以 Server-Sent Events 格式发送
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
            
            # 发送结束信号
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            log.error(f"流式对话失败: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """
    获取对话历史
    """
    history = rag_service.get_history(session_id)
    
    if history is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return {
        "session_id": session_id,
        "messages": history
    }


@router.delete("/chat/session/{session_id}")
async def delete_session(session_id: str):
    """
    删除会话
    """
    rag_service.clear_session(session_id)
    
    return {
        "message": "会话已删除",
        "session_id": session_id
    }


# ========== Agent 智能对话端点（具体路由在前，通用路由在后）==========

@router.post("/chat/agent/new_session/{paper_id}")
async def create_agent_session(paper_id: str):
    """
    创建新的 Agent 对话会话
    """
    session_id = agent_service.create_session(paper_id)
    
    return {
        "session_id": session_id,
        "paper_id": paper_id,
        "message": "Agent 会话创建成功"
    }


@router.get("/chat/agent/history/{session_id}")
async def get_agent_history(session_id: str):
    """
    获取 Agent 对话历史
    """
    history = agent_service.get_history(session_id)
    
    if history is None:
        raise HTTPException(status_code=404, detail="Agent 会话不存在")
    
    return {
        "session_id": session_id,
        "messages": history
    }


@router.delete("/chat/agent/session/{session_id}")
async def delete_agent_session(session_id: str):
    """
    删除 Agent 会话
    """
    agent_service.clear_session(session_id)
    
    return {
        "message": "Agent 会话已删除",
        "session_id": session_id
    }


@router.post("/chat/agent/{paper_id}")
async def agent_chat_with_paper(
    paper_id: str,
    request: AgentChatRequest
):
    """
    Agent 智能对话（流式输出，包含推理过程）
    
    返回 Server-Sent Events 流，事件类型包括：
    - thinking: 推理过程（意图识别、检索策略等）
    - retrieval: 检索状态
    - evaluation: 完备性评估结果
    - content: 最终回答内容
    - sources: 引用来源
    - done: 完成标志
    - error: 错误信息
    """
    async def generate():
        """Agent 流式生成器"""
        try:
            async for event in agent_service.chat_stream(
                paper_id=paper_id,
                question=request.message,
                session_id=request.session_id,
                provider=request.provider.value if request.provider else None
            ):
                # 以 Server-Sent Events 格式发送
                event_data = {
                    "type": event.type,
                    "content": event.content
                }
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            log.error(f"Agent 对话失败: {e}")
            error_event = {"type": "error", "content": str(e)}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        }
    )


# ========== 通用对话端点（放在最后）==========

@router.post("/chat/{paper_id}", response_model=ChatResponse)
async def chat_with_paper(
    paper_id: str,
    request: ChatRequest
):
    """
    与论文对话（非流式）
    
    注意：此路由必须放在所有 /chat/xxx/{param} 路由之后，
    因为 {paper_id} 会匹配任何路径段。
    """
    try:
        session_id, answer, sources = await rag_service.chat(
            paper_id=paper_id,
            question=request.message,
            session_id=request.session_id,
            provider=request.provider.value if request.provider else None,
            stream=False
        )
        
        response = ChatResponse(
            session_id=session_id,
            message=ChatMessage(
                role="assistant",
                content=answer,
                timestamp=datetime.now()
            ),
            sources=sources
        )
        
        return response
        
    except Exception as e:
        log.error(f"对话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
