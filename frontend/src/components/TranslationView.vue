<template>
  <div class="translation-view">
    <div class="card-modern overflow-hidden">
      <!-- Header -->
      <div class="px-5 py-4 border-b border-base-300/50 flex justify-between items-center bg-base-100">
        <h2 class="font-heading font-bold text-lg flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24"
            stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
          </svg>
          论文翻译
        </h2>
        <div class="flex gap-2">
          <button v-if="!paperStore.hasTranslation && !translating" class="btn btn-primary btn-sm rounded-xl gap-1"
            @click="startTranslation">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24"
              stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            开始翻译
          </button>
          <div v-if="translating" class="flex items-center gap-2 text-sm text-base-content/60">
            <span class="loading loading-spinner loading-sm text-primary"></span>
            翻译中...
          </div>
        </div>
      </div>

      <!-- Content -->
      <div class="p-5 bg-base-200/30">
        <!-- Translation Content -->
        <div v-if="paperStore.hasTranslation" class="space-y-4">
          <!-- View Mode Toggle -->
          <div class="flex gap-1 p-1 bg-base-100 rounded-xl w-fit border border-base-300/50">
            <button v-for="mode in viewModes" :key="mode.id"
              class="px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200" :class="viewMode === mode.id
                ? 'bg-primary text-primary-content shadow-sm'
                : 'text-base-content/60 hover:text-base-content hover:bg-base-200'" @click="viewMode = mode.id">
              {{ mode.label }}
            </button>
          </div>

          <!-- Segments -->
          <div class="space-y-4">
            <div v-for="(segment, index) in paperStore.translation.segments" :key="index"
              class="bg-base-100 rounded-xl border border-base-300/50 overflow-hidden">
              <!-- Section Title -->
              <div v-if="segment.section_title" class="px-5 py-3 bg-base-200/50 border-b border-base-300/50">
                <h3 class="font-heading font-semibold text-base">{{ segment.section_title }}</h3>
              </div>

              <!-- Bilingual View -->
              <div v-if="viewMode === 'bilingual'"
                class="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-base-300/50">
                <div class="p-5">
                  <div class="text-xs font-medium text-base-content/50 mb-2 flex items-center gap-1">
                    <span class="w-1.5 h-1.5 rounded-full bg-neutral"></span>
                    原文
                  </div>
                  <MarkdownRenderer :content="segment.original" class="text-sm text-base-content/80" />
                </div>
                <div class="p-5">
                  <div class="text-xs font-medium text-base-content/50 mb-2 flex items-center gap-1">
                    <span class="w-1.5 h-1.5 rounded-full bg-primary"></span>
                    译文
                  </div>
                  <MarkdownRenderer :content="segment.translated" class="text-sm text-base-content/80" />
                </div>
              </div>

              <!-- Translation Only -->
              <div v-else-if="viewMode === 'translation'" class="p-5">
                <MarkdownRenderer :content="segment.translated" class="text-sm text-base-content/80" />
              </div>

              <!-- Original Only -->
              <div v-else class="p-5">
                <MarkdownRenderer :content="segment.original" class="text-sm text-base-content/80" />
              </div>
            </div>
          </div>
        </div>

        <!-- Error Message -->
        <div v-if="errorMessage" class="mb-4 p-4 bg-error/10 border border-error/30 rounded-xl text-error text-sm">
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24"
              stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {{ errorMessage }}
          </div>
        </div>

        <!-- Empty State -->
        <div v-else-if="!translating && !paperStore.hasTranslation" class="text-center py-16">
          <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-primary/10 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-primary" fill="none" viewBox="0 0 24 24"
              stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
            </svg>
          </div>
          <p class="text-base-content/60">点击"开始翻译"按钮生成论文译文</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { usePaperStore } from '../stores/paper'
import MarkdownRenderer from './MarkdownRenderer.vue'
import api from '../api/client'

const props = defineProps({
  paperId: {
    type: String,
    required: true
  }
})

const paperStore = usePaperStore()
const viewMode = ref('bilingual')
const translating = ref(false)
const errorMessage = ref('')

const viewModes = [
  { id: 'bilingual', label: '双语对照' },
  { id: 'translation', label: '仅译文' },
  { id: 'original', label: '仅原文' }
]

onMounted(async () => {
  await paperStore.loadTranslation(props.paperId)
})

async function startTranslation() {
  translating.value = true
  errorMessage.value = ''
  try {
    const result = await paperStore.requestTranslation(props.paperId)

    // 如果已有翻译结果，直接加载
    if (result.status === 'completed') {
      await paperStore.loadTranslation(props.paperId)
      return
    }

    // 轮询翻译状态（同步阻塞方式，与 SummaryPanel 一致）
    await pollTranslationStatus(result.task_id)
  } catch (e) {
    console.error('翻译失败:', e)
    errorMessage.value = e.message
  } finally {
    translating.value = false
  }
}

async function pollTranslationStatus(taskId) {
  const maxAttempts = 120  // 最多轮询 120 次（约 6 分钟）
  const interval = 3000    // 每 3 秒轮询一次

  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(resolve => setTimeout(resolve, interval))

    try {
      const status = await api.getTranslationStatus(taskId)
      console.log(`翻译状态 (${i + 1}/${maxAttempts}):`, status)

      if (status.status === 'completed') {
        await paperStore.loadTranslation(props.paperId)
        return
      } else if (status.status === 'failed') {
        throw new Error(status.error || '翻译失败，请重试')
      }
      // 继续轮询
    } catch (e) {
      // 404 表示任务不存在，可能还没开始，继续等待
      if (e.message !== '任务不存在') {
        throw e
      }
    }
  }

  throw new Error('翻译超时，请稍后刷新页面查看结果')
}
</script>
