"""
Pytest 配置文件
共享 fixtures 和测试配置
"""
import pytest
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环 fixture"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def embedding_service():
    """创建 EmbeddingService fixture"""
    from app.services.embedding_service import create_embedding_service
    return create_embedding_service()


@pytest.fixture
def milvus_service():
    """创建 MilvusService fixture"""
    from app.services.milvus_service import MilvusService
    return MilvusService()


@pytest.fixture
def sample_texts():
    """示例测试文本"""
    return [
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning is a subset of artificial intelligence.",
        "Python is a popular programming language for data science.",
    ]


@pytest.fixture
def sample_chinese_texts():
    """示例中文测试文本"""
    return [
        "人工智能是计算机科学的一个分支。",
        "自然语言处理技术可以帮助计算机理解人类语言。",
        "深度学习模型需要大量的训练数据。",
    ]

