"""
向量化服务
将论文文本块向量化并存储到 Milvus
"""
from typing import List, Optional

from app.models.schemas import PaperStructure, TextChunk
from app.services.text_processor import text_processor
from app.services.embedding_service import create_embedding_service
from app.services.milvus_service import milvus_service
from app.utils.logger import log
from app.utils.async_helper import TaskQueue


class VectorizationService:
    """向量化服务"""
    
    async def vectorize_and_store_paper(
        self,
        paper: PaperStructure,
        embedding_provider: Optional[str] = None,
        embedding_model: Optional[str] = None
    ) -> int:
        """
        向量化论文并存储到 Milvus
        
        Args:
            paper: 论文结构
            embedding_provider: Embedding 提供商
            embedding_model: Embedding 模型
            
        Returns:
            存储的块数量
        """
        log.info(f"开始向量化论文: {paper.paper_id}")
        
        # 1. 文本分块
        chunks = text_processor.create_chunks_from_paper(paper, preserve_sections=True)
        
        if not chunks:
            log.warning(f"论文 {paper.paper_id} 没有可分块的内容")
            return 0
        
        log.info(f"论文分块完成: {len(chunks)} 个块")
        
        # 2. 创建 Embedding 服务
        embedding_service = create_embedding_service(
            provider=embedding_provider,
            model=embedding_model
        )
        
        # 3. 获取 Embedding 维度并初始化 Milvus collection
        dimension = embedding_service.get_dimension()
        await milvus_service.create_collection(dimension=dimension)
        
        # 4. 批量生成 Embeddings
        texts = [chunk.text for chunk in chunks]
        embeddings = await embedding_service.embed_batch(texts)
        
        log.info(f"Embedding 生成完成: {len(embeddings)} 个向量")
        
        # 5. 准备数据并插入 Milvus
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        paper_ids = [chunk.paper_id for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]
        
        await milvus_service.insert_chunks(
            chunk_ids=chunk_ids,
            paper_ids=paper_ids,
            texts=texts,
            embeddings=embeddings,
            metadatas=metadatas
        )
        
        log.info(f"论文 {paper.paper_id} 向量化完成: 共存储 {len(chunks)} 个块")
        return len(chunks)
    
    async def delete_paper_vectors(self, paper_id: str) -> int:
        """
        删除论文的所有向量
        
        Args:
            paper_id: 论文ID
            
        Returns:
            删除的数量
        """
        count = await milvus_service.delete_by_paper_id(paper_id)
        log.info(f"删除论文 {paper_id} 的向量: {count} 个")
        return count
    
    async def search_similar_chunks(
        self,
        query_text: str,
        paper_id: Optional[str] = None,
        top_k: int = 5,
        section_filter: Optional[List[str]] = None,
        embedding_provider: Optional[str] = None,
        embedding_model: Optional[str] = None
    ) -> List[dict]:
        """
        搜索相似的文本块
        
        Args:
            query_text: 查询文本
            paper_id: 可选的论文ID限制
            top_k: 返回结果数量
            section_filter: 可选的章节标题过滤列表
            embedding_provider: Embedding 提供商
            embedding_model: Embedding 模型
            
        Returns:
            搜索结果列表
        """
        # 生成查询向量
        embedding_service = create_embedding_service(
            provider=embedding_provider,
            model=embedding_model
        )
        
        query_embedding = await embedding_service.embed_text(query_text)
        
        # 搜索相似向量（增加 top_k 以便后续过滤）
        search_top_k = top_k * 2 if section_filter else top_k
        
        results = await milvus_service.search(
            query_embedding=query_embedding,
            top_k=search_top_k,
            paper_id=paper_id
        )
        
        # 如果有章节过滤，进行后处理过滤
        if section_filter and results:
            filtered_results = []
            section_filter_lower = [s.lower() for s in section_filter]
            
            for result in results:
                section_title = result.get("metadata", {}).get("section_title", "").lower()
                # 模糊匹配：检查章节标题是否包含过滤词
                if any(filter_term in section_title or section_title in filter_term 
                       for filter_term in section_filter_lower):
                    filtered_results.append(result)
                
                if len(filtered_results) >= top_k:
                    break
            
            # 如果过滤后结果太少，补充未过滤的结果
            if len(filtered_results) < top_k:
                for result in results:
                    if result not in filtered_results:
                        filtered_results.append(result)
                        if len(filtered_results) >= top_k:
                            break
            
            results = filtered_results[:top_k]
        else:
            results = results[:top_k]
        
        log.info(f"搜索完成: 查询='{query_text[:50]}...', 结果数={len(results)}")
        return results
    
    async def search_multi_keywords(
        self,
        keywords: List[str],
        paper_id: Optional[str] = None,
        top_k: int = 5,
        section_filter: Optional[List[str]] = None,
        embedding_provider: Optional[str] = None,
        embedding_model: Optional[str] = None
    ) -> List[dict]:
        """
        多关键词搜索并合并去重结果
        
        Args:
            keywords: 关键词列表
            paper_id: 可选的论文ID限制
            top_k: 每个关键词返回结果数量
            section_filter: 可选的章节标题过滤列表
            embedding_provider: Embedding 提供商
            embedding_model: Embedding 模型
            
        Returns:
            合并去重后的搜索结果列表
        """
        all_results = []
        seen_chunks = set()
        
        for keyword in keywords:
            results = await self.search_similar_chunks(
                query_text=keyword,
                paper_id=paper_id,
                top_k=top_k,
                section_filter=section_filter,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model
            )
            
            for result in results:
                chunk_id = result.get("chunk_id")
                if chunk_id and chunk_id not in seen_chunks:
                    seen_chunks.add(chunk_id)
                    all_results.append(result)
        
        # 按相关度排序
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        log.info(f"多关键词搜索完成: 关键词数={len(keywords)}, 去重后结果数={len(all_results)}")
        return all_results


# 全局服务实例
vectorization_service = VectorizationService()

