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
      console.log('[SSE] 开始请求 Agent 流式对话')
      const response = await api.agentChatStream(paperId, {
        message,
        session_id: sessionId
      })
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('[SSE] HTTP 错误响应:', errorText)
        throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`)
      }
      
      if (!response.body) {
        console.error('[SSE] 响应体为空')
        throw new Error('响应体为空')
      }
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let contentBuffer = ''
      let sources = []
      let eventCount = 0
      
      console.log('[SSE] 开始读取流数据')
      
      while (true) {
        const { done, value } = await reader.read()
        
        if (done) {
          console.log('[SSE] 流读取完成，共收到', eventCount, '个事件')
          break
        }
        
        if (value) {
          const chunk = decoder.decode(value, { stream: true })
          buffer += chunk
          
          // 解析 SSE 事件 - 按 \n\n 分割事件
          const events = buffer.split('\n\n')
          buffer = events.pop() || '' // 保留未完成的事件
          
          for (const eventText of events) {
            if (!eventText.trim()) {
              console.log('[SSE] 跳过空事件')
              continue
            }
            
            // 查找 data: 行
            const lines = eventText.split('\n')
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const jsonStr = line.slice(6).trim()
                  if (!jsonStr) {
                    console.log('[SSE] 跳过空的data行')
                    continue
                  }
                  
                  const data = JSON.parse(jsonStr)
                  const { type, content } = data
                  eventCount++
                  
                  agentStatus.value = type
                  
                  switch (type) {
                    case 'thinking':
                      agentThinking.value.push({ type: 'thinking', content })
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
                  console.error('[SSE] 解析事件失败:', e, '原始行:', line)
                }
              }
            }
          }
        }
      }
      
      // 确保流结束时设置状态
      if (sessions.value[sessionId].messages[assistantMsgIndex].isStreaming) {
        sessions.value[sessionId].messages[assistantMsgIndex].isStreaming = false
        agentStatus.value = ''
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
