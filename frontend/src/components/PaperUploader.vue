<template>
  <div class="paper-uploader">
    <!-- URL Input -->
    <div class="mb-6">
      <label class="block text-sm font-medium text-base-content/70 mb-2">
        论文 URL（如 arXiv 链接）
      </label>
      <div class="flex gap-2">
        <input 
          v-model="url" 
          type="text" 
          placeholder="https://arxiv.org/pdf/..." 
          class="input input-bordered flex-1 rounded-xl bg-base-100 focus:border-primary focus:ring-2 focus:ring-primary/20"
          :disabled="uploading || parsing"
          @keypress.enter="submitUrl"
        />
        <button 
          class="btn btn-primary rounded-xl px-6"
          @click="submitUrl"
          :disabled="!url || uploading || parsing"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          解析
        </button>
      </div>
    </div>

    <!-- 
      文件上传功能暂时屏蔽
      原因：MinerU API 只支持通过 URL 解析 PDF，需要公网可访问的文件地址
      待有公网地址后，将 v-if="false" 改为 v-if="true" 即可启用
    -->
    
    <!-- Divider (暂时屏蔽) -->
    <div v-if="false" class="relative my-8">
      <div class="absolute inset-0 flex items-center">
        <div class="w-full border-t border-base-300"></div>
      </div>
      <div class="relative flex justify-center text-sm">
        <span class="px-4 bg-base-100 text-base-content/50">或</span>
      </div>
    </div>

    <!-- File Upload (暂时屏蔽) -->
    <div v-if="false">
      <label class="block text-sm font-medium text-base-content/70 mb-2">
        上传 PDF 文件
      </label>
      
      <!-- 已上传文件信息 -->
      <div v-if="uploadedFile" class="border-2 border-success/50 rounded-2xl p-6 bg-success/5">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-xl bg-success/20 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p class="font-medium text-base-content">{{ uploadedFile.filename }}</p>
              <p class="text-sm text-base-content/50">{{ formatFileSize(uploadedFile.file_size) }}</p>
            </div>
          </div>
          <div class="flex gap-2">
            <button 
              v-if="!parsing"
              class="btn btn-ghost btn-sm rounded-lg"
              @click="clearUploadedFile"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
              取消
            </button>
            <button 
              class="btn btn-primary rounded-lg px-6"
              @click="startParse"
              :disabled="parsing"
            >
              <span v-if="!parsing" class="flex items-center gap-1">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                开始解析
              </span>
              <span v-else class="flex items-center gap-2">
                <span class="loading loading-spinner loading-sm"></span>
                解析中...
              </span>
            </button>
          </div>
        </div>
        
        <!-- 解析进度 -->
        <div v-if="parsing" class="mt-4">
          <p class="text-sm text-base-content/70 mb-2">{{ statusMessage }}</p>
          <div v-if="progress > 0" class="w-full">
            <div class="h-2 bg-base-200 rounded-full overflow-hidden">
              <div 
                class="h-full bg-primary rounded-full transition-all duration-300"
                :style="{ width: `${progress}%` }"
              ></div>
            </div>
            <p class="text-xs text-base-content/50 mt-1 text-right">{{ progress }}%</p>
          </div>
        </div>
      </div>
      
      <!-- 拖拽上传区域 -->
      <div 
        v-else
        class="relative border-2 border-dashed rounded-2xl p-8 text-center transition-all duration-200 cursor-pointer"
        :class="dragOver 
          ? 'border-primary bg-primary/5' 
          : 'border-base-300 hover:border-primary/50 hover:bg-base-200/50'"
        @dragover.prevent="dragOver = true"
        @dragleave.prevent="dragOver = false"
        @drop.prevent="handleDrop"
        @click="$refs.fileInput.click()"
      >
        <input 
          ref="fileInput" 
          type="file" 
          accept=".pdf" 
          class="hidden"
          @change="handleFileSelect"
        />
        
        <div v-if="!uploading">
          <div class="w-14 h-14 mx-auto mb-4 rounded-2xl bg-primary/10 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-7 w-7 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <p class="font-medium text-base-content mb-1">点击或拖拽 PDF 文件到此处</p>
          <p class="text-sm text-base-content/50">最大支持 50MB</p>
        </div>
        
        <div v-else class="space-y-4">
          <div class="loading loading-spinner loading-lg text-primary"></div>
          <p class="font-medium text-base-content">{{ statusMessage }}</p>
        </div>
      </div>
    </div>

    <!-- Error Message -->
    <div v-if="error" class="mt-4 p-4 bg-error/10 border border-error/20 rounded-xl">
      <div class="flex items-center gap-2 text-error">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span class="text-sm font-medium">{{ error }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api/client'

const emit = defineEmits(['uploaded'])

const url = ref('')
const dragOver = ref(false)
const uploading = ref(false)
const parsing = ref(false)
const progress = ref(0)
const statusMessage = ref('')
const error = ref(null)
const fileInput = ref(null)
const uploadedFile = ref(null) // { file_id, filename, file_size }

// 格式化文件大小
function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(2) + ' MB'
}

// URL 解析（直接开始解析，因为 URL 方式没有大小限制）
async function submitUrl() {
  if (!url.value) return
  
  parsing.value = true
  error.value = null
  statusMessage.value = '正在提交解析任务...'
  
  try {
    const result = await api.parseUrl(url.value)
    await pollStatus(result.task_id)
  } catch (e) {
    error.value = e.message
    parsing.value = false
  }
}

function handleDrop(e) {
  dragOver.value = false
  const files = e.dataTransfer.files
  if (files.length > 0 && files[0].type === 'application/pdf') {
    uploadFile(files[0])
  }
}

function handleFileSelect(e) {
  const files = e.target.files
  if (files.length > 0) {
    uploadFile(files[0])
  }
}

// 只上传文件，不开始解析
async function uploadFile(file) {
  if (!file || file.type !== 'application/pdf') {
    error.value = '请选择 PDF 文件'
    return
  }
  
  if (file.size > 50 * 1024 * 1024) {
    error.value = '文件大小不能超过 50MB'
    return
  }
  
  uploading.value = true
  error.value = null
  statusMessage.value = '正在上传文件...'
  
  try {
    const result = await api.uploadPaper(file)
    // 上传成功，保存文件信息，等待用户点击解析
    uploadedFile.value = {
      file_id: result.file_id,
      filename: result.filename,
      file_size: result.file_size
    }
    uploading.value = false
    statusMessage.value = ''
  } catch (e) {
    error.value = e.message
    uploading.value = false
  }
}

// 清除已上传的文件
function clearUploadedFile() {
  uploadedFile.value = null
  error.value = null
  // 清空 file input
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

// 开始解析已上传的文件
async function startParse() {
  if (!uploadedFile.value) return
  
  parsing.value = true
  error.value = null
  progress.value = 0
  statusMessage.value = '正在提交解析任务...'
  
  try {
    const result = await api.startParse(uploadedFile.value.file_id)
    await pollStatus(result.task_id)
  } catch (e) {
    error.value = e.message
    parsing.value = false
  }
}

async function pollStatus(taskId) {
  const maxAttempts = 200 // 最多轮询约 10 分钟（200 * 3秒）
  let attempts = 0
  
  statusMessage.value = '正在解析论文...'
  
  const poll = async () => {
    try {
      const status = await api.getParseStatus(taskId)
      progress.value = status.progress || 0
      
      if (status.status === 'completed') {
        statusMessage.value = '解析完成！'
        parsing.value = false
        uploadedFile.value = null
        emit('uploaded', status.paper_id)
        return
      } else if (status.status === 'failed') {
        error.value = status.error || '解析失败'
        parsing.value = false
        return
      }
      
      attempts++
      if (attempts < maxAttempts) {
        setTimeout(poll, 3000)
      } else {
        error.value = '解析超时，请稍后重试'
        parsing.value = false
      }
    } catch (e) {
      error.value = e.message
      parsing.value = false
    }
  }
  
  poll()
}
</script>
