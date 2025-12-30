import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api/client'

export const useChatStore = defineStore('chat', () => {
  // State
  const sessions = ref({}) // { sessionId: { paperId, messages } }
  const currentSessionId = ref(null)
  
  // Agent 推理状态
  const agentThinking = ref([])   // 推理过程记录
  const agentStatus = ref('')      // 当前状态: thinking, retrieval, evaluation, content
  const isAgentMode = ref(true)    // 是否使用 Agent 模式

  // Actions
  async function createSession(paperId) {
    // 根据模式选择创建会话的 API
    const data = isAgentMode.value 
      ? await api.createAgentSession(paperId)
      : await api.createChatSession(paperId)
    const sessionId = data.session_id
    
    sessions.value[sessionId] = {
      paperId,
      messages: []
    }
    
    currentSessionId.value = sessionId
    return sessionId
  }

  // 普通 RAG 对话
  async function sendMessage(paperId, message, sessionId = null) {
    let sid = sessionId || currentSessionId.value

    // 如果没有 session_id，先创建一个
    if (!sid) {
      sid = await createSession(paperId)
    }

    // 确保 currentSessionId 已设置
    currentSessionId.value = sid

    // 添加用户消息
    if (!sessions.value[sid]) {
      sessions.value[sid] = { paperId, messages: [] }
    }

    // 添加用户消息
    sessions.value[sid].messages.push({
      role: 'user',
      content: message,
      timestamp: new Date()
    })

    // 根据模式选择不同的对话方式
    if (isAgentMode.value) {
      return await sendAgentMessage(paperId, message, sid)
    }

    // 普通 RAG 对话
    const response = await api.chatWithPaper(paperId, {
      message,
      session_id: sid,
      stream: false
    })

    console.log('收到响应:', response)

    const content = response.message?.content || response.content || response.answer || '无响应'
    
    sessions.value[sid].messages.push({
      role: 'assistant',
      content: typeof content === 'string' ? content : JSON.stringify(content),
      sources: response.sources || [],
      timestamp: new Date()
    })

    return response
  }

  // Agent 流式对话
  async function sendAgentMessage(paperId, message, sessionId) {
    // 重置推理状态
    agentThinking.value = []
    agentStatus.value = 'thinking'
    
    // 先添加一个空的助手消息占位
    const assistantMsgIndex = sessions.value[sessionId].messages.length
    sessions.value[sessionId].messages.push({
      role: 'assistant',
      content: '',
      thinking: [],
      sources: [],
      timestamp: new Date(),
      isStreaming: true
    })
    
    try {
      const response = await api.agentChatStream(paperId, {
        message,
        session_id: sessionId
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let contentBuffer = ''
      let sources = []
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        
        // 解析 SSE 事件
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // 保留未完成的行
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              const { type, content } = data
              
              agentStatus.value = type
              
              switch (type) {
                case 'thinking':
                  agentThinking.value.push({ type: 'thinking', content })
                  // 更新消息中的 thinking
                  sessions.value[sessionId].messages[assistantMsgIndex].thinking = [...agentThinking.value]
                  break
                  
                case 'retrieval':
                  agentThinking.value.push({ type: 'retrieval', content })
                  sessions.value[sessionId].messages[assistantMsgIndex].thinking = [...agentThinking.value]
                  break
                  
                case 'evaluation':
                  agentThinking.value.push({ type: 'evaluation', content })
                  sessions.value[sessionId].messages[assistantMsgIndex].thinking = [...agentThinking.value]
                  break
                  
                case 'content':
                  contentBuffer += content
                  sessions.value[sessionId].messages[assistantMsgIndex].content = contentBuffer
                  break
                  
                case 'sources':
                  sources = content
                  sessions.value[sessionId].messages[assistantMsgIndex].sources = sources
                  break
                  
                case 'done':
                  sessions.value[sessionId].messages[assistantMsgIndex].isStreaming = false
                  agentStatus.value = ''
                  break
                  
                case 'error':
                  throw new Error(content)
              }
            } catch (e) {
              if (e.message !== 'Unexpected end of JSON input') {
                console.error('解析 SSE 事件失败:', e, line)
              }
            }
          }
        }
      }
      
      return { content: contentBuffer, sources }
      
    } catch (error) {
      console.error('Agent 对话失败:', error)
      sessions.value[sessionId].messages[assistantMsgIndex].content = `错误: ${error.message}`
      sessions.value[sessionId].messages[assistantMsgIndex].isStreaming = false
      agentStatus.value = ''
      throw error
    }
  }

  function getSessionMessages(sessionId) {
    return sessions.value[sessionId]?.messages || []
  }

  function clearSession(sessionId) {
    if (sessionId && sessions.value[sessionId]) {
      delete sessions.value[sessionId]
    }
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = null
    }
    agentThinking.value = []
    agentStatus.value = ''
  }
  
  function setAgentMode(enabled) {
    isAgentMode.value = enabled
  }

  return {
    sessions,
    currentSessionId,
    agentThinking,
    agentStatus,
    isAgentMode,
    createSession,
    sendMessage,
    sendAgentMessage,
    getSessionMessages,
    clearSession,
    setAgentMode
  }
})
