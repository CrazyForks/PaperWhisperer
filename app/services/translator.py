"""
论文翻译服务
提供高质量的学术论文翻译
"""
from typing import List, Dict, Optional, Tuple
import asyncio

from app.models.schemas import PaperStructure, PaperSection, TranslationSegment, TranslationResult, TaskStatus
from app.services.llm_factory import llm_factory
from app.utils.logger import log
from datetime import datetime


class TranslationService:
    """翻译服务"""
    
    # 需要跳过翻译的章节标题关键词（遇到这些章节后，后续所有章节都跳过）
    STOP_SECTIONS = [
        'references', 'bibliography', '参考文献'
    ]
    
    # 需要跳过但不影响后续章节的关键词
    SKIP_SECTIONS = [
        'acknowledgments', 'acknowledgements', '致谢'
    ]
    
    # 并发限制
    MAX_CONCURRENT_TRANSLATIONS = 10
    
    # 翻译 Prompt 模板
    TRANSLATION_PROMPT = """你是一位专业的学术论文翻译专家。请将以下{source_lang}学术论文文本翻译成{target_lang}。

翻译要求：
1. 保持学术专业性和严谨性
2. 专业术语翻译准确，保持一致性
3. 语句流畅自然，符合目标语言的学术表达习惯
4. 保留原文的公式、引用格式和特殊标记
5. 不要添加任何解释或额外内容，只返回翻译结果

原文：
{text}

翻译："""
    
    CONTEXT_PROMPT = """请注意，这是论文的一部分，以下是上下文信息：

前文片段：
{prev_context}

当前需要翻译的文本：
{text}

后文片段：
{next_context}

请根据上下文翻译当前文本，确保术语和表达的连贯性。只返回当前文本的翻译，不要翻译上下文部分。"""
    
    def _should_stop_at_section(self, title: str) -> bool:
        """
        检查是否应该在此章节停止翻译（后续章节都不翻译）
        
        Args:
            title: 章节标题
            
        Returns:
            是否应该停止
        """
        title_lower = title.lower().strip()
        return any(stop in title_lower for stop in self.STOP_SECTIONS)
    
    def _should_skip_section(self, title: str) -> bool:
        """
        检查是否应该跳过此章节（但继续翻译后续章节）
        
        Args:
            title: 章节标题
            
        Returns:
            是否应该跳过
        """
        title_lower = title.lower().strip()
        return any(skip in title_lower for skip in self.SKIP_SECTIONS)
    
    def _filter_sections(self, sections: List[PaperSection]) -> Tuple[List[PaperSection], int]:
        """
        过滤需要翻译的章节
        
        Args:
            sections: 所有章节列表
            
        Returns:
            (需要翻译的章节列表, 被跳过的章节数)
        """
        filtered = []
        skipped_count = 0
        stop_found = False
        
        for section in sections:
            # 如果已经遇到了停止标记，跳过后续所有章节
            if stop_found:
                skipped_count += 1
                continue
            
            # 检查是否是停止章节
            if self._should_stop_at_section(section.title):
                log.info(f"遇到 References 章节，停止翻译后续内容: {section.title}")
                stop_found = True
                skipped_count += 1
                continue
            
            # 检查是否是需要跳过的章节
            if self._should_skip_section(section.title):
                log.info(f"跳过章节: {section.title}")
                skipped_count += 1
                continue
            
            # 跳过空内容的章节
            if not section.content or not section.content.strip():
                skipped_count += 1
                continue
            
            filtered.append(section)
        
        return filtered, skipped_count
    
    async def translate_text(
        self,
        text: str,
        source_lang: str = "英文",
        target_lang: str = "中文",
        provider: Optional[str] = None,
        prev_context: Optional[str] = None,
        next_context: Optional[str] = None
    ) -> str:
        """
        翻译单段文本
        
        Args:
            text: 要翻译的文本
            source_lang: 源语言
            target_lang: 目标语言
            provider: LLM 提供商
            prev_context: 前文上下文
            next_context: 后文上下文
            
        Returns:
            翻译结果
        """
        # 构建 prompt
        if prev_context or next_context:
            prompt = self.CONTEXT_PROMPT.format(
                prev_context=prev_context or "(无)",
                text=text,
                next_context=next_context or "(无)"
            )
        else:
            prompt = self.TRANSLATION_PROMPT.format(
                source_lang=source_lang,
                target_lang=target_lang,
                text=text
            )
        
        messages = [
            {"role": "system", "content": "你是专业的学术论文翻译专家。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await llm_factory.chat(
                messages=messages,
                provider=provider,
                temperature=0.3,  # 较低温度以提高一致性
                stream=False
            )
            
            return result.strip()
            
        except Exception as e:
            log.error(f"翻译失败: {e}")
            raise
    
    async def _translate_section(
        self,
        section: PaperSection,
        source_lang: str,
        target_lang: str,
        provider: Optional[str]
    ) -> List[TranslationSegment]:
        """
        翻译单个章节
        
        Args:
            section: 章节对象
            source_lang: 源语言
            target_lang: 目标语言
            provider: LLM 提供商
            
        Returns:
            翻译片段列表
        """
        # 如果章节内容为空，直接返回空列表，防止 LLM 幻觉
        if not section.content or not section.content.strip():
            log.info(f"跳过空内容章节: {section.title}")
            return []
        
        # 如果章节内容太长，需要分段
        if len(section.content) > 3000:  # 字符数限制
            return await self._translate_long_section(
                section.content,
                section.title,
                source_lang,
                target_lang,
                provider
            )
        else:
            # 翻译整个章节
            translated = await self.translate_text(
                text=section.content,
                source_lang=source_lang,
                target_lang=target_lang,
                provider=provider
            )
            
            segment = TranslationSegment(
                original=section.content,
                translated=translated,
                section_title=section.title
            )
            return [segment]
    
    async def translate_paper(
        self,
        paper: PaperStructure,
        source_lang: str = "英文",
        target_lang: str = "中文",
        provider: Optional[str] = None,
        translate_by_section: bool = True
    ) -> TranslationResult:
        """
        翻译整篇论文（并行执行）
        
        Args:
            paper: 论文结构
            source_lang: 源语言
            target_lang: 目标语言
            provider: LLM 提供商
            translate_by_section: 是否按章节翻译
            
        Returns:
            翻译结果
        """
        log.info(f"开始翻译论文: {paper.paper_id}, 原始章节数: {len(paper.sections)}")
        
        segments: List[TranslationSegment] = []
        
        try:
            if translate_by_section and paper.sections:
                # 过滤需要翻译的章节
                sections_to_translate, skipped_count = self._filter_sections(paper.sections)
                log.info(f"过滤后需要翻译的章节数: {len(sections_to_translate)}, 跳过章节数: {skipped_count}")
                
                if not sections_to_translate:
                    log.warning("没有需要翻译的章节")
                    return TranslationResult(
                        paper_id=paper.paper_id,
                        segments=[],
                        status=TaskStatus.COMPLETED,
                        created_at=datetime.now()
                    )
                
                # 使用信号量限制并发数
                semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_TRANSLATIONS)
                
                async def translate_with_limit(idx: int, section: PaperSection) -> Tuple[int, List[TranslationSegment]]:
                    """带并发限制的翻译任务"""
                    async with semaphore:
                        log.info(f"开始翻译章节 {idx+1}/{len(sections_to_translate)}: {section.title}")
                        try:
                            result = await self._translate_section(
                                section,
                                source_lang,
                                target_lang,
                                provider
                            )
                            log.info(f"完成翻译章节 {idx+1}/{len(sections_to_translate)}: {section.title}")
                            return (idx, result)
                        except Exception as e:
                            log.error(f"章节翻译失败 {section.title}: {e}")
                            # 返回空列表，继续其他翻译
                            return (idx, [])
                
                # 创建所有翻译任务并并行执行
                tasks = [
                    translate_with_limit(idx, section) 
                    for idx, section in enumerate(sections_to_translate)
                ]
                
                # 并行执行所有翻译任务
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 按原始顺序排序结果
                sorted_results = sorted(
                    [(idx, segs) for idx, segs in results if isinstance((idx, segs), tuple)],
                    key=lambda x: x[0]
                )
                
                # 合并所有翻译片段
                for idx, segs in sorted_results:
                    if segs:
                        segments.extend(segs)
                
            else:
                # 全文翻译（分段处理）
                full_text = paper.full_content
                subsegments = await self._translate_long_section(
                    full_text,
                    None,
                    source_lang,
                    target_lang,
                    provider
                )
                segments.extend(subsegments)
            
            result = TranslationResult(
                paper_id=paper.paper_id,
                segments=segments,
                status=TaskStatus.COMPLETED,
                created_at=datetime.now()
            )
            
            log.info(f"论文翻译完成: {paper.paper_id}, 段落数: {len(segments)}")
            return result
            
        except Exception as e:
            log.error(f"论文翻译失败: {e}")
            result = TranslationResult(
                paper_id=paper.paper_id,
                segments=segments,  # 保存已翻译的部分
                status=TaskStatus.FAILED,
                created_at=datetime.now()
            )
            return result
    
    async def _translate_long_section(
        self,
        text: str,
        section_title: Optional[str],
        source_lang: str,
        target_lang: str,
        provider: Optional[str]
    ) -> List[TranslationSegment]:
        """
        翻译长文本（分段并行处理，保留上下文）
        
        Args:
            text: 文本内容
            section_title: 章节标题
            source_lang: 源语言
            target_lang: 目标语言
            provider: LLM 提供商
            
        Returns:
            翻译片段列表
        """
        # 按段落分割
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        if not paragraphs:
            return []
        
        context_size = 200  # 上下文字符数
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_TRANSLATIONS)
        
        async def translate_paragraph(idx: int, para: str) -> Tuple[int, TranslationSegment]:
            """带并发限制的段落翻译"""
            async with semaphore:
                # 获取上下文
                prev_context = paragraphs[idx-1][-context_size:] if idx > 0 else None
                next_context = paragraphs[idx+1][:context_size] if idx < len(paragraphs) - 1 else None
                
                # 翻译段落
                translated = await self.translate_text(
                    text=para,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    provider=provider,
                    prev_context=prev_context,
                    next_context=next_context
                )
                
                segment = TranslationSegment(
                    original=para,
                    translated=translated,
                    section_title=section_title
                )
                return (idx, segment)
        
        # 创建所有翻译任务并并行执行
        tasks = [translate_paragraph(idx, para) for idx, para in enumerate(paragraphs)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 按原始顺序排序结果
        sorted_results = sorted(
            [(idx, seg) for idx, seg in results if isinstance((idx, seg), tuple) and seg],
            key=lambda x: x[0]
        )
        
        return [seg for idx, seg in sorted_results]
    
    async def translate_abstract(
        self,
        abstract: str,
        source_lang: str = "英文",
        target_lang: str = "中文",
        provider: Optional[str] = None
    ) -> str:
        """
        翻译摘要（快速翻译）
        
        Args:
            abstract: 摘要文本
            source_lang: 源语言
            target_lang: 目标语言
            provider: LLM 提供商
            
        Returns:
            翻译后的摘要
        """
        return await self.translate_text(
            text=abstract,
            source_lang=source_lang,
            target_lang=target_lang,
            provider=provider
        )


# 全局服务实例
translation_service = TranslationService()
