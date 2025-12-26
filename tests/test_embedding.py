"""
Embedding 服务测试
测试 embedding 接口的各项功能
"""
import pytest
from app.services.embedding_service import EmbeddingService, create_embedding_service
from app.config import settings


class TestEmbeddingService:
    """Embedding 服务测试类"""
    
    @pytest.fixture
    def service(self):
        """创建 EmbeddingService fixture"""
        return create_embedding_service()
    
    @pytest.mark.asyncio
    async def test_initialization(self, service):
        """测试 1: 初始化服务"""
        assert service is not None
        assert service.provider is not None
        assert service.model is not None
        assert service.config["base_url"] is not None
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_single_embedding(self, service):
        """测试 2: 单个文本的 embedding"""
        test_text = "This is a test sentence for embedding generation."
        
        embedding = await service.embed_text(test_text)
        
        assert embedding is not None
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        
        # 验证维度
        expected_dim = service.get_dimension()
        assert len(embedding) == expected_dim
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_batch_embedding(self, service, sample_texts):
        """测试 3: 批量文本的 embedding"""
        embeddings = await service.embed_batch(sample_texts)
        
        assert embeddings is not None
        assert len(embeddings) == len(sample_texts)
        
        # 验证所有向量维度一致
        dims = [len(emb) for emb in embeddings]
        assert len(set(dims)) == 1
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_empty_input(self, service):
        """测试 4: 空输入处理"""
        embeddings = await service.embed_batch([])
        assert embeddings == []
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chinese_text(self, service, sample_chinese_texts):
        """测试 5: 中文文本 embedding"""
        embeddings = await service.embed_batch(sample_chinese_texts)
        
        assert embeddings is not None
        assert len(embeddings) == len(sample_chinese_texts)
        assert len(embeddings[0]) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_long_text(self, service):
        """测试 6: 长文本 embedding"""
        # 生成一个较长的文本（约500个单词）
        long_text = " ".join([
            "Artificial intelligence and machine learning have revolutionized "
            "the way we approach complex problems in various domains."
        ] * 50)
        
        embedding = await service.embed_text(long_text)
        
        assert embedding is not None
        assert len(embedding) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_dimension_consistency(self, service):
        """测试 7: 不同文本长度的维度一致性"""
        test_texts = [
            "Short.",
            "This is a medium length sentence.",
            "This is a much longer sentence that contains significantly more words "
            "and information than the previous ones.",
        ]
        
        embeddings = []
        for text in test_texts:
            emb = await service.embed_text(text)
            embeddings.append(emb)
        
        # 检查维度是否一致
        dims = [len(emb) for emb in embeddings]
        assert len(set(dims)) == 1
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_large_batch(self, service):
        """测试 8: 大批量文本 embedding (分批处理)"""
        # 生成25个测试文本，会分3批处理（10+10+5）
        batch_size = 25
        test_texts = [
            f"This is test sentence number {i} for batch embedding." 
            for i in range(batch_size)
        ]
        
        embeddings = await service.embed_batch(test_texts)
        
        assert embeddings is not None
        assert len(embeddings) == batch_size


class TestEmbeddingServiceUnit:
    """Embedding 服务单元测试（不需要 API 调用）"""
    
    def test_create_service(self):
        """测试: 创建服务实例"""
        service = create_embedding_service()
        assert isinstance(service, EmbeddingService)
    
    def test_provider_config(self):
        """测试: 配置加载"""
        config = settings.get_embedding_config()
        assert "api_key" in config
        assert "base_url" in config
        assert "model" in config
    
    def test_default_provider(self):
        """测试: 默认提供商设置"""
        assert settings.default_embedding_provider is not None
        assert settings.default_embedding_model is not None

