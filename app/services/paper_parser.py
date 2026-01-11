"""
论文解析器
从 MinerU 返回的内容中提取论文结构和元数据
"""
import re
import json
from typing import Dict, Any, List
from datetime import datetime

from app.models.schemas import PaperMetadata, PaperSection, PaperStructure
from app.services.llm_factory import llm_factory
from app.utils.logger import log


class PaperParser:
    """论文解析器"""
    
    @staticmethod
    def replace_image_paths(markdown_content: str, paper_id: str) -> str:
        """
        将 Markdown 中的相对图片路径替换为 API 路径
        
        Args:
            markdown_content: Markdown 内容
            paper_id: 论文ID
            
        Returns:
            替换后的 Markdown 内容
        """
        # 匹配 Markdown 图片语法: ![alt](images/xxx.jpg) 或 ![alt](./images/xxx.jpg)
        # 替换为: ![alt](/api/images/{paper_id}/images/xxx.jpg)
        pattern = r'!\[([^\]]*)\]\((?:\./)?images/([^)]+)\)'
        replacement = rf'![\1](/api/images/{paper_id}/images/\2)'
        
        return re.sub(pattern, replacement, markdown_content)
    
    # 元数据提取 Prompt 模板
    METADATA_EXTRACTION_PROMPT = """请从以下学术论文内容中提取元数据信息。

论文内容：
{content}

请严格按照以下 JSON 格式返回结果，不要添加任何其他文字说明：
{{
    "title": "原始论文标题（如果找不到则返回 null）",
    "title_cn": "中文标题（如果原标题不是中文，则翻译成中文；如果原标题已经是中文，则与 title 保持一致）",
    "authors": ["作者1", "作者2", "..."]（如果找不到则返回空数组 []），
    "abstract": "论文摘要内容（如果找不到则返回 null）",
    "keywords": ["关键词1", "关键词2", "..."]（如果找不到则返回空数组 []）
}}

注意：
1. 标题通常出现在论文开头，可能是最大的标题
2. title_cn 必须是中文标题，如果原标题是英文等非中文语言，请翻译成中文
3. 作者信息可能包含机构信息，注意提取完整
4. 摘要通常在 Abstract 或"摘要"标题下
5. 关键词通常在 Keywords 或"关键词"标题后

请直接返回 JSON，不要有任何前缀或后缀文字。"""

    @staticmethod
    async def extract_metadata_with_llm(markdown_content: str) -> Dict[str, Any]:
        """
        使用大模型从 Markdown 内容中提取元数据
        
        Args:
            markdown_content: Markdown 格式的论文内容
            
        Returns:
            元数据字典
        """
        # 只取前 5000 字符，节省 token
        content_for_llm = markdown_content[:5000]
        
        prompt = PaperParser.METADATA_EXTRACTION_PROMPT.format(content=content_for_llm)
        
        messages = [
            {"role": "system", "content": "你是专业的学术论文分析专家，擅长从论文中提取结构化信息。请始终返回有效的 JSON 格式。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await llm_factory.chat(
                messages=messages,
                temperature=0.1,  # 低温度确保稳定输出
                max_tokens=1000,
                stream=False
            )
            
            # 清理结果，提取 JSON 部分
            result = result.strip()
            
            # 尝试处理可能被 markdown 代码块包裹的情况
            if result.startswith("```"):
                # 移除 markdown 代码块标记
                lines = result.split('\n')
                result = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
                result = result.strip()
            
            # 解析 JSON
            metadata = json.loads(result)
            
            # 确保返回的格式正确
            return {
                "title": metadata.get("title"),
                "title_cn": metadata.get("title_cn"),
                "authors": metadata.get("authors", []) or [],
                "abstract": metadata.get("abstract"),
                "keywords": metadata.get("keywords", []) or []
            }
            
        except json.JSONDecodeError as e:
            log.warning(f"LLM 返回的内容无法解析为 JSON: {e}, 原始内容: {result[:200]}")
            raise
        except Exception as e:
            log.error(f"使用 LLM 提取元数据失败: {e}")
            raise
    
    @staticmethod
    def _extract_metadata_regex(markdown_content: str) -> Dict[str, Any]:
        """
        使用正则表达式从 Markdown 内容中提取元数据（备用方法）
        
        Args:
            markdown_content: Markdown 格式的论文内容
            
        Returns:
            元数据字典
        """
        metadata = {
            "title": None,
            "title_cn": None,
            "authors": [],
            "abstract": None,
            "keywords": []
        }
        
        lines = markdown_content.split('\n')
        
        # 提取标题（通常是第一个 # 标题）
        for line in lines[:20]:  # 只检查前20行
            if line.startswith('# ') and not metadata["title"]:
                metadata["title"] = line[2:].strip()
                # 正则方法无法翻译，title_cn 保持与 title 相同
                metadata["title_cn"] = metadata["title"]
                break
        
        # 提取摘要（查找 Abstract 章节）
        abstract_pattern = r'(?:^|\n)#{1,3}\s*(?:Abstract|ABSTRACT|摘要)\s*\n(.*?)(?=\n#{1,3}\s|\Z)'
        abstract_match = re.search(abstract_pattern, markdown_content, re.DOTALL | re.IGNORECASE)
        if abstract_match:
            abstract_text = abstract_match.group(1).strip()
            # 清理多余的空行
            abstract_text = re.sub(r'\n\s*\n', '\n', abstract_text)
            metadata["abstract"] = abstract_text[:2000]  # 限制长度
        
        # 提取作者（查找常见的作者模式）
        author_pattern = r'(?:^|\n)(?:Authors?|作者)[\s:：]*(.*?)(?=\n|$)'
        author_match = re.search(author_pattern, markdown_content[:2000], re.IGNORECASE)
        if author_match:
            authors_text = author_match.group(1)
            # 尝试分割作者名（通过逗号、分号或 and）
            authors = re.split(r'[,;]|\s+and\s+', authors_text)
            metadata["authors"] = [a.strip() for a in authors if a.strip()]
        
        # 提取关键词
        keywords_pattern = r'(?:^|\n)(?:Keywords?|关键词)[\s:：]*(.*?)(?=\n|$)'
        keywords_match = re.search(keywords_pattern, markdown_content[:3000], re.IGNORECASE)
        if keywords_match:
            keywords_text = keywords_match.group(1)
            keywords = re.split(r'[,;·]', keywords_text)
            metadata["keywords"] = [k.strip() for k in keywords if k.strip()]
        
        return metadata
    
    @staticmethod
    def extract_sections(markdown_content: str) -> List[Dict[str, Any]]:
        """
        从 Markdown 内容中提取章节结构
        
        Args:
            markdown_content: Markdown 格式的论文内容
            
        Returns:
            章节列表
        """
        sections = []
        
        # 匹配标题行（# ## ### 等）
        header_pattern = r'^(#{1,6})\s+(.+?)$'
        
        lines = markdown_content.split('\n')
        current_section = None
        section_order = 0
        
        for i, line in enumerate(lines):
            match = re.match(header_pattern, line)
            
            if match:
                # 保存上一个章节
                if current_section:
                    sections.append(current_section)
                
                # 开始新章节
                level = len(match.group(1))
                title = match.group(2).strip()
                
                current_section = {
                    "section_id": f"section_{section_order}",
                    "title": title,
                    "level": level,
                    "order": section_order,
                    "content": "",
                    "start_line": i
                }
                section_order += 1
            
            elif current_section:
                # 添加内容到当前章节
                current_section["content"] += line + "\n"
        
        # 保存最后一个章节
        if current_section:
            sections.append(current_section)
        
        # 清理内容
        for section in sections:
            section["content"] = section["content"].strip()
        
        return sections
    
    @staticmethod
    async def parse_result(paper_id: str, mineru_result: Dict[str, Any]) -> PaperStructure:
        """
        解析 MinerU 返回的结果，生成论文结构
        
        Args:
            paper_id: 论文ID
            mineru_result: MinerU 返回的结果
            
        Returns:
            PaperStructure 对象
        """
        try:
            # 获取 Markdown 内容
            if "content" in mineru_result:
                markdown_content = mineru_result["content"]
            elif isinstance(mineru_result, str):
                markdown_content = mineru_result
            else:
                markdown_content = str(mineru_result)
            
            # 替换图片路径为 API 路径
            markdown_content = PaperParser.replace_image_paths(markdown_content, paper_id)
            
            # 使用 LLM 提取元数据，失败时回退到正则方法
            try:
                log.info(f"使用 LLM 提取论文元数据: {paper_id}")
                metadata_dict = await PaperParser.extract_metadata_with_llm(markdown_content)
                log.info(f"LLM 元数据提取成功: {paper_id}")
            except Exception as e:
                log.warning(f"LLM 提取元数据失败，回退到正则方法: {e}")
                metadata_dict = PaperParser._extract_metadata_regex(markdown_content)
            
            title = metadata_dict.get("title") or f"Paper {paper_id}"
            title_cn = metadata_dict.get("title_cn") or title
            
            metadata = PaperMetadata(
                paper_id=paper_id,
                title=title,
                title_cn=title_cn,
                authors=metadata_dict.get("authors"),
                abstract=metadata_dict.get("abstract"),
                keywords=metadata_dict.get("keywords"),
                created_at=datetime.now()
            )
            
            # 提取章节
            sections_data = PaperParser.extract_sections(markdown_content)
            
            sections = [
                PaperSection(
                    section_id=s["section_id"],
                    title=s["title"],
                    content=s["content"],
                    level=s["level"],
                    order=s["order"]
                )
                for s in sections_data
            ]
            
            # 构建完整结构
            paper_structure = PaperStructure(
                paper_id=paper_id,
                metadata=metadata,
                sections=sections,
                full_content=markdown_content
            )
            
            log.info(f"论文解析完成: {paper_id}, 标题: {metadata.title}, 章节数: {len(sections)}")
            return paper_structure
            
        except Exception as e:
            log.error(f"解析论文结构失败: {e}", exc_info=True)
            raise
    
    @staticmethod
    def merge_short_sections(sections: List[PaperSection], min_length: int = 200) -> List[PaperSection]:
        """
        合并过短的章节（用于后续处理）
        
        Args:
            sections: 章节列表
            min_length: 最小章节长度
            
        Returns:
            合并后的章节列表
        """
        if not sections:
            return []
        
        merged = [sections[0]]
        
        for section in sections[1:]:
            last_section = merged[-1]
            
            # 如果上一个章节太短，且当前章节层级更深或相同，则合并
            if (len(last_section.content) < min_length and 
                section.level >= last_section.level):
                last_section.content += f"\n\n## {section.title}\n\n{section.content}"
            else:
                merged.append(section)
        
        return merged


# 全局解析器实例
paper_parser = PaperParser()

