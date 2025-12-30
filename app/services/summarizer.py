"""
摘要生成服务
直接基于论文内容生成综合摘要
"""
from typing import List, Dict, Optional
import asyncio

from app.models.schemas import PaperStructure, PaperSummary, SectionSummary
from app.services.llm_factory import llm_factory
from app.utils.logger import log
from datetime import datetime


class SummarizerService:
    """摘要生成服务"""
    
    # Prompt 模板
    SECTION_SUMMARY_PROMPT = """请为以下学术论文章节生成简洁的摘要（200-300字）。

章节标题：{title}

章节内容：
{content}

请提炼该章节的核心内容、主要观点和关键发现。"""
    
    COMPREHENSIVE_SUMMARY_PROMPT = """基于以下论文的各章节摘要，生成一篇完整的综合摘要（500-800字）。

论文标题：{title}

章节摘要：
{section_summaries}

请全面概括论文的：
1. 研究背景和动机
2. 核心方法和技术
3. 主要实验和结果
4. 贡献和创新点
5. 局限性和未来工作

综合摘要："""

    # 直接摘要 Prompt（跳过 Map 阶段，直接基于论文内容生成）
    DIRECT_SUMMARY_PROMPT = """请为以下学术论文生成一篇完整的综合摘要（500-800字）。

论文标题：{title}

论文摘要：
{abstract}

论文主要内容：
{content}

请全面概括论文的：
1. 研究背景和动机
2. 核心方法和技术
3. 主要实验和结果
4. 贡献和创新点
5. 局限性和未来工作

综合摘要："""
    
    KEY_POINTS_PROMPT = """请从以下论文摘要中提取5-8个关键要点，每个要点用一句话概括。

论文摘要：
{summary}

关键要点（使用 JSON 列表格式）："""
    
    METHODOLOGY_PROMPT = """请总结以下论文的研究方法（200-300字）。

论文内容：
{content}

方法总结："""
    
    CONTRIBUTIONS_PROMPT = """请总结以下论文的主要贡献和创新点（200-300字）。

论文内容：
{content}

贡献总结："""
    
    async def summarize_section(
        self,
        section_title: str,
        section_content: str,
        provider: Optional[str] = None
    ) -> str:
        """
        生成章节摘要
        
        Args:
            section_title: 章节标题
            section_content: 章节内容
            provider: LLM 提供商
            
        Returns:
            章节摘要
        """
        # 如果内容太长，截断
        max_length = 4000
        if len(section_content) > max_length:
            section_content = section_content[:max_length] + "...(内容已截断)"
        
        prompt = self.SECTION_SUMMARY_PROMPT.format(
            title=section_title,
            content=section_content
        )
        
        messages = [
            {"role": "system", "content": "你是专业的学术论文分析专家。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await llm_factory.chat(
                messages=messages,
                provider=provider,
                temperature=0.5,
                stream=False
            )
            
            return result.strip()
            
        except Exception as e:
            log.error(f"生成章节摘要失败: {e}")
            raise
    
    async def generate_comprehensive_summary(
        self,
        title: str,
        section_summaries: List[str],
        provider: Optional[str] = None
    ) -> str:
        """
        生成综合摘要（Reduce 阶段）
        
        Args:
            title: 论文标题
            section_summaries: 章节摘要列表
            provider: LLM 提供商
            
        Returns:
            综合摘要
        """
        summaries_text = "\n\n".join([
            f"章节 {i+1}：{summary}"
            for i, summary in enumerate(section_summaries)
        ])
        
        prompt = self.COMPREHENSIVE_SUMMARY_PROMPT.format(
            title=title,
            section_summaries=summaries_text
        )
        
        messages = [
            {"role": "system", "content": "你是专业的学术论文分析专家。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await llm_factory.chat(
                messages=messages,
                provider=provider,
                temperature=0.5,
                max_tokens=1500,
                stream=False
            )
            
            return result.strip()
            
        except Exception as e:
            log.error(f"生成综合摘要失败: {e}")
            raise
    
    async def generate_direct_summary(
        self,
        title: str,
        abstract: str,
        content: str,
        provider: Optional[str] = None
    ) -> str:
        """
        直接基于论文内容生成综合摘要（跳过 Map 阶段）
        
        Args:
            title: 论文标题
            abstract: 论文摘要
            content: 论文主要内容
            provider: LLM 提供商
            
        Returns:
            综合摘要
        """
        # 限制内容长度
        max_content_length = 8000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "...(内容已截断)"
        
        prompt = self.DIRECT_SUMMARY_PROMPT.format(
            title=title,
            abstract=abstract or "无摘要",
            content=content
        )
        
        messages = [
            {"role": "system", "content": "你是专业的学术论文分析专家。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await llm_factory.chat(
                messages=messages,
                provider=provider,
                temperature=0.5,
                max_tokens=1500,
                stream=False
            )
            
            return result.strip()
            
        except Exception as e:
            log.error(f"生成直接摘要失败: {e}")
            raise
    
    async def extract_key_points(
        self,
        summary: str,
        provider: Optional[str] = None
    ) -> List[str]:
        """
        提取关键要点
        
        Args:
            summary: 论文摘要
            provider: LLM 提供商
            
        Returns:
            关键要点列表
        """
        prompt = self.KEY_POINTS_PROMPT.format(summary=summary)
        
        messages = [
            {"role": "system", "content": "你是专业的学术论文分析专家。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await llm_factory.chat(
                messages=messages,
                provider=provider,
                temperature=0.3,
                stream=False
            )
            
            # 尝试解析 JSON 列表
            import json
            import re
            
            # 移除可能的 Markdown 代码块标记
            cleaned_result = result.strip()
            # 匹配 ```json ... ``` 或 ``` ... ``` 格式
            code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned_result)
            if code_block_match:
                cleaned_result = code_block_match.group(1).strip()
            
            try:
                key_points = json.loads(cleaned_result)
                if isinstance(key_points, list):
                    return key_points
            except:
                pass
            
            # 如果不是 JSON，按行分割
            lines = [line.strip() for line in cleaned_result.split('\n') if line.strip()]
            # 移除列表标记（如 "1. ", "- " 等）
            key_points = [re.sub(r'^[\d\-\*\+\.]+\s*', '', line) for line in lines]
            return [kp for kp in key_points if kp]
            
        except Exception as e:
            log.error(f"提取关键要点失败: {e}")
            return []
    
    async def summarize_methodology(
        self,
        content: str,
        provider: Optional[str] = None
    ) -> str:
        """
        总结研究方法
        
        Args:
            content: 论文内容（通常是方法章节）
            provider: LLM 提供商
            
        Returns:
            方法总结
        """
        # 截断内容
        max_length = 4000
        if len(content) > max_length:
            content = content[:max_length] + "...(内容已截断)"
        
        prompt = self.METHODOLOGY_PROMPT.format(content=content)
        
        messages = [
            {"role": "system", "content": "你是专业的学术论文分析专家。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await llm_factory.chat(
                messages=messages,
                provider=provider,
                temperature=0.5,
                stream=False
            )
            
            return result.strip()
            
        except Exception as e:
            log.error(f"总结方法失败: {e}")
            return ""
    
    async def summarize_contributions(
        self,
        content: str,
        provider: Optional[str] = None
    ) -> str:
        """
        总结主要贡献
        
        Args:
            content: 论文内容（通常是结论或摘要）
            provider: LLM 提供商
            
        Returns:
            贡献总结
        """
        # 截断内容
        max_length = 4000
        if len(content) > max_length:
            content = content[:max_length] + "...(内容已截断)"
        
        prompt = self.CONTRIBUTIONS_PROMPT.format(content=content)
        
        messages = [
            {"role": "system", "content": "你是专业的学术论文分析专家。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await llm_factory.chat(
                messages=messages,
                provider=provider,
                temperature=0.5,
                stream=False
            )
            
            return result.strip()
            
        except Exception as e:
            log.error(f"总结贡献失败: {e}")
            return ""
    
    async def summarize_paper(
        self,
        paper: PaperStructure,
        provider: Optional[str] = None,
        summary_type: str = "comprehensive"
    ) -> PaperSummary:
        """
        生成论文摘要（优化版：跳过章节摘要，直接生成综合摘要）
        
        Args:
            paper: 论文结构
            provider: LLM 提供商
            summary_type: 摘要类型（comprehensive/brief/technical）
            
        Returns:
            论文摘要对象
        """
        log.info(f"开始生成论文摘要: {paper.paper_id}, 类型: {summary_type}")
        
        try:
            # 提取关键章节内容用于生成摘要
            # 只提取 Introduction、Methods、Results、Discussion、Conclusion 等关键章节
            key_section_keywords = [
                'introduction', 'abstract', 'method', 'approach', 'result', 
                'experiment', 'discussion', 'conclusion', 'summary',
                '引言', '介绍', '方法', '结果', '实验', '讨论', '结论', '总结'
            ]
            
            key_content_parts = []
            for section in paper.sections:
                title_lower = section.title.lower()
                # 只提取关键章节或前几个章节
                is_key_section = any(kw in title_lower for kw in key_section_keywords)
                if is_key_section and len(section.content) >= 100:
                    # 每个章节最多取前2000字符
                    content_preview = section.content[:2000]
                    key_content_parts.append(f"## {section.title}\n{content_preview}")
            
            # 如果没有匹配到关键章节，使用全文的前8000字符
            if not key_content_parts:
                combined_content = paper.full_content[:8000] if paper.full_content else ""
            else:
                combined_content = "\n\n".join(key_content_parts)
            
            # 直接生成综合摘要（跳过 Map 阶段）
            overall_summary = await self.generate_direct_summary(
                title=paper.metadata.title or "未知标题",
                abstract=paper.metadata.abstract or "",
                content=combined_content,
                provider=provider
            )
            
            # 提取关键要点
            key_points = await self.extract_key_points(overall_summary, provider=provider)
            
            # 构建最终摘要对象（不再生成章节摘要、方法总结和贡献总结，大幅提升速度）
            paper_summary = PaperSummary(
                paper_id=paper.paper_id,
                overall_summary=overall_summary,
                key_points=key_points,
                methodology=None,
                contributions=None,
                section_summaries=[],  # 不再生成章节摘要
                created_at=datetime.now()
            )
            
            log.info(f"论文摘要生成完成: {paper.paper_id}")
            return paper_summary
            
        except Exception as e:
            log.error(f"生成论文摘要失败: {e}")
            raise


# 全局服务实例
summarizer_service = SummarizerService()

