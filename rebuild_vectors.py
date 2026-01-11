#!/usr/bin/env python3
"""
重建向量索引脚本
从已解析的论文 JSON 文件重新生成向量并存入 Milvus
"""
import asyncio
import json
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from app.models.schemas import PaperStructure
from app.services.vectorization_service import vectorization_service
from app.utils.logger import log


async def rebuild_paper_vectors(paper_id: str = None):
    """
    重建论文向量
    
    Args:
        paper_id: 指定论文ID，如果为 None 则重建所有论文
    """
    parsed_dir = settings.parsed_dir
    
    if paper_id:
        # 重建指定论文
        json_file = parsed_dir / f"{paper_id}.json"
        if not json_file.exists():
            log.error(f"论文文件不存在: {json_file}")
            return
        json_files = [json_file]
    else:
        # 重建所有论文
        json_files = list(parsed_dir.glob("*.json"))
    
    if not json_files:
        log.warning("没有找到任何论文文件")
        return
    
    log.info(f"找到 {len(json_files)} 个论文文件，开始重建向量...")
    
    success_count = 0
    fail_count = 0
    
    for json_file in json_files:
        try:
            log.info(f"处理: {json_file.name}")
            
            # 读取论文数据
            with open(json_file, "r", encoding="utf-8") as f:
                paper_data = json.load(f)
            
            # 如果顶层没有 paper_id，从 metadata 中提取
            if "paper_id" not in paper_data and "metadata" in paper_data:
                paper_data["paper_id"] = paper_data["metadata"].get("paper_id")
            
            # 转换为 PaperStructure
            paper = PaperStructure(**paper_data)
            
            # 向量化并存储
            chunk_count = await vectorization_service.vectorize_and_store_paper(paper)
            
            log.info(f"✓ 论文 {paper.paper_id} 完成，存储了 {chunk_count} 个向量块")
            success_count += 1
            
        except Exception as e:
            log.error(f"✗ 处理失败 {json_file.name}: {e}")
            fail_count += 1
    
    log.info(f"\n重建完成！成功: {success_count}, 失败: {fail_count}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="重建论文向量索引")
    parser.add_argument("--paper-id", "-p", help="指定论文ID，不指定则重建所有论文")
    args = parser.parse_args()
    
    asyncio.run(rebuild_paper_vectors(args.paper_id))
