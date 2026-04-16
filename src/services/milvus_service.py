import os
from pathlib import Path
from typing import Any
from loguru import logger
from datetime import datetime
from pydantic import BaseModel, Field
from transformers import AutoTokenizer
from optimum.onnxruntime import ORTModelForCustomTasks
from pymilvus import AsyncMilvusClient, AnnSearchRequest, WeightedRanker, DataType

from src.utils import utils
from src.config import settings
from src.context import trans_id_ctx


class ProjectFileSearchResult(BaseModel):
    """项目文件搜索结果
    
    包含文件 ID、相似度距离、项目 ID、文件信息等。
    """
    id: int = Field(description="搜索结果ID")
    distance: float = Field(description="与查询向量的距离/相似度")
    project_id: str = Field(description="所属项目ID")
    name: str = Field(description="文件名")
    path: str = Field(description="文件路径")
    type: str = Field(description="文件类型")
    content: str = Field(description="文件内容")
    summary: str = Field(description="文件摘要")
    create_time: str = Field(description="创建时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class ProjectContextSearchResult(BaseModel):
    """项目上下文搜索结果
    
    包含对话上下文 ID、相似度距离、项目 ID、内容等。
    """
    id: int = Field(description="搜索结果ID")
    distance: float = Field(description="与查询向量的距离/相似度")
    project_id: str = Field(description="所属项目ID")
    content: str = Field(description="对话上下文内容")
    create_time: str = Field(description="创建时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class BGE3ONNXModel:
    """BGE-M3 ONNX INT8 量化模型封装
    
    使用 BGE-M3 模型生成稠密和稀疏向量，
    支持 ONNX 推理加速和 INT8 量化。
    """

    def __init__(self, model_name: str, local_path: Path | None = None):
        """初始化 ONNX 模型
        
        Args:
            model_name: HuggingFace 模型名称
            local_path: 本地模型路径（优先使用）
        """
        self.model_name = model_name
        self.local_path = local_path
        self.model = None
        self.tokenizer = None
        self._init_model()

    def _init_model(self) -> None:
        """初始化 ONNX 推理模型和分词器"""
        # 创建本地目录
        self.local_path.mkdir(parents=True, exist_ok=True)

        # 加载分词器
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            cache_dir=str(self.local_path)
        )

        # 加载 ONNX 模型
        self.model = ORTModelForCustomTasks.from_pretrained(
            self.model_name,
            file_name="model_quantized.onnx",
            cache_dir=str(self.local_path)
        )
        logger.info(f"{self.model_name} 模型加载完成")

    def encode(self, texts: list[str], batch_size: int = 8) -> dict[str, Any]:
        """生成文本的稠密和稀疏向量
        
        Args:
            texts: 文本列表
            batch_size: 批处理大小
            
        Returns:
            {"dense": [[...], ...], "sparse": [{token_id: weight, ...}, ...]}
        """
        dense_embeddings = []
        lexical_weights = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]

            # Tokenize
            # batch_texts.shape=(math.ceil(len(texts)/batch_size),)
            # inputs.shape=(math.ceil(len(texts)/batch_size),seq_len)
            inputs = self.tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="np"
            )

            # ONNX 推理
            outputs = self.model(**inputs)

            # 获取稠密向量
            # dense_vecs.shape=(batch, 1024)
            dense_vecs = outputs.dense_vecs
            for j in range(len(batch_texts)):
                dense_embeddings.append(dense_vecs[j].tolist())

            # 获取稀疏向量
            # sparse_vecs.shape=(batch, seq_len, 1)
            # input_ids.shape=(batch, seq_len)
            sparse_vecs = outputs.sparse_vecs
            input_ids = inputs["input_ids"]

            for j in range(len(batch_texts)):
                sparse = {}
                seq_len = sparse_vecs.shape[1]
                for k in range(seq_len):
                    weight = float(sparse_vecs[j, k, 0])
                    token_id = int(input_ids[j, k])
                    if weight > 0 and token_id > 0:
                        sparse[token_id] = weight
                lexical_weights.append(sparse)

        # dense_embeddings.shape=(len(texts),1024)
        # lexical_weights.shape=(len(texts))
        return {
            "dense": dense_embeddings,
            "sparse": lexical_weights
        }

    def __call__(self, texts: list[str]) -> dict[str, Any]:
        """支持直接调用"""
        return self.encode(texts)


class MilvusService:
    """Milvus-lite 混合搜索服务
    
    使用 BGE-M3 INT8 量化模型进行混合检索，
    支持稠密向量和稀疏向量的加权搜索。
    提供项目文件和对话上下文的向量存储和检索功能。
    """

    def __init__(self):
        """初始化 Milvus 服务"""
        self._client: AsyncMilvusClient | None = None
        self._embedding_fn: BGE3ONNXModel | None = None

    async def initialize(self) -> None:
        """初始化数据库
        
        初始化 Milvus 客户端、嵌入模型和 Collection。
        """
        self._init_database()
        await self._init_collections()

    def _init_database(self) -> None:
        """初始化 Milvus 客户端和嵌入模型"""
        # 确保目录存在
        settings.milvus_database_path.parent.mkdir(parents=True, exist_ok=True)

        # 初始化 Milvus 客户端
        self._client = AsyncMilvusClient(uri=str(settings.milvus_database_path))
        logger.info(f"Milvus 客户端初始化完成，数据库路径:{settings.milvus_database_path}")

        # 初始化 BGE-M3 INT8 量化模型
        self._embedding_fn = BGE3ONNXModel(
            model_name=settings.embedding_model_name,
            local_path=settings.embedding_model_local_path
        )
        logger.info(f"{settings.embedding_model_name} 量化模型初始化完成")

    async def _init_collections(self) -> None:
        """初始化两个 Collection
        
        创建 project_file 和 project_context 两个 Collection，
        用于存储文件向量和对话上下文向量。
        """
        # project_file Collection
        if not await self._client.has_collection(settings.milvus_project_file_collection_name):
            schema = self._client.create_schema(auto_id=True, enable_dynamic_field=False)
            schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
            schema.add_field(field_name="sql_db_id", datatype=DataType.VARCHAR, max_length=64)
            schema.add_field(field_name="project_id", datatype=DataType.VARCHAR, max_length=64)
            schema.add_field(field_name="name", datatype=DataType.VARCHAR, max_length=256)
            schema.add_field(field_name="path", datatype=DataType.VARCHAR, max_length=1024)
            schema.add_field(field_name="type", datatype=DataType.VARCHAR, max_length=32)
            schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)
            schema.add_field(field_name="summary", datatype=DataType.VARCHAR, max_length=4096)
            schema.add_field(field_name="content_dense_vector", datatype=DataType.FLOAT_VECTOR, dim=1024)
            schema.add_field(field_name="content_sparse_vector", datatype=DataType.SPARSE_FLOAT_VECTOR)
            schema.add_field(field_name="create_time", datatype=DataType.VARCHAR, max_length=32)
            schema.add_field(field_name="metadata", datatype=DataType.JSON)

            index_params = self._client.prepare_index_params()
            index_params.add_index(field_name="content_dense_vector", index_type="AUTOINDEX", metric_type="COSINE")
            index_params.add_index(field_name="content_sparse_vector", index_type="SPARSE_INVERTED_INDEX",
                                   metric_type="IP")

            await self._client.create_collection(
                collection_name=settings.milvus_project_file_collection_name,
                schema=schema,
                index_params=index_params
            )
            logger.info(f"Collection:{settings.milvus_project_file_collection_name} 创建完成")
        else:
            logger.info(f"Collection:{settings.milvus_project_file_collection_name} 已存在")

        # project_context Collection
        if not await self._client.has_collection(settings.milvus_project_context_collection_name):
            schema = self._client.create_schema(auto_id=True, enable_dynamic_field=False)
            schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
            schema.add_field(field_name="project_id", datatype=DataType.VARCHAR, max_length=64)
            schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)
            schema.add_field(field_name="content_dense_vector", datatype=DataType.FLOAT_VECTOR, dim=1024)
            schema.add_field(field_name="content_sparse_vector", datatype=DataType.SPARSE_FLOAT_VECTOR)
            schema.add_field(field_name="create_time", datatype=DataType.VARCHAR, max_length=32)
            schema.add_field(field_name="metadata", datatype=DataType.JSON)

            index_params = self._client.prepare_index_params()
            index_params.add_index(field_name="content_dense_vector", index_type="AUTOINDEX", metric_type="COSINE")
            index_params.add_index(field_name="content_sparse_vector", index_type="SPARSE_INVERTED_INDEX",
                                   metric_type="IP")

            await self._client.create_collection(
                collection_name=settings.milvus_project_context_collection_name,
                schema=schema,
                index_params=index_params
            )
            logger.info(f"Collection:{settings.milvus_project_context_collection_name} 创建完成")
        else:
            logger.info(f"Collection:{settings.milvus_project_context_collection_name} 已存在")

    def _embed_texts(self, texts: list[str]) -> dict[str, Any]:
        """使用 BGE-M3 ONNX 生成稠密和稀疏向量
        
        Args:
            texts: 文本列表
            
        Returns:
            {"dense": [[...]], "sparse": [{token_id: weight}, ...]}
            
        Raises:
            RuntimeError: 服务未正确初始化
        """
        if self._embedding_fn is None:
            raise RuntimeError("MilvusService 未正确初始化")
        return self._embedding_fn(texts)

    async def add_project_file(
            self,
            sql_db_id: str,
            project_id: str,
            name: str,
            path: str,
            type: str,
            content: str,
            summary: str,
            metadata: dict[str, Any] | None = None
    ) -> int:
        """添加项目文件到向量数据库
        
        Args:
            sql_db_id: 业务数据库 ID
            project_id: 项目 ID
            name: 文件名
            path: 文件路径
            type: 文件类型
            content: 文件内容
            summary: 文件摘要
            metadata: 额外元数据
            
        Returns:
            插入的实体 ID
        """
        # 生成向量
        embeddings = self._embed_texts([content])

        # 准备数据
        data = [{
            "content_dense_vector": embeddings["dense"][0],
            "content_sparse_vector": embeddings["sparse"][0],
            "sql_db_id": sql_db_id,
            "project_id": project_id,
            "name": name,
            "path": path,
            "type": type,
            "content": content,
            "summary": summary,
            "create_time": datetime.now().isoformat(),
            "metadata": metadata or {}
        }]

        # 插入
        result = await self._client.insert(
            collection_name=settings.milvus_project_file_collection_name,
            data=data
        )
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 方法名:{utils.get_func_name()} 项目Id:{project_id} 插入项目文件:{name}")
        return result["ids"][0]

    async def add_project_context(
            self,
            project_id: str,
            content: str,
            metadata: dict[str, Any] | None = None
    ) -> int:
        """添加对话上下文到向量数据库
        
        Args:
            project_id: 项目 ID
            content: 总结后的对话内容
            metadata: 额外元数据
            
        Returns:
            插入的实体 ID
        """
        # 生成向量
        embeddings = self._embed_texts([content])

        # 准备数据
        data = [{
            "content_dense_vector": embeddings["dense"][0],
            "content_sparse_vector": embeddings["sparse"][0],
            "project_id": project_id,
            "content": content,
            "create_time": datetime.now().isoformat(),
            "metadata": metadata or {}
        }]

        # 插入
        result = await self._client.insert(
            collection_name=settings.milvus_project_context_collection_name,
            data=data
        )
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 方法名:{utils.get_func_name()} 项目Id:{project_id} 插入上下文对话:{content}")
        return result["ids"][0]

    async def search_project_files(
            self,
            query: str,
            project_id: str | None = None,
            limit: int = 5
    ) -> list[ProjectFileSearchResult]:
        """混合搜索项目文件
        
        使用稠密和稀疏向量进行混合检索。
        
        Args:
            query: 查询文本
            project_id: 可选，按项目 ID 过滤
            limit: 返回数量
            
        Returns:
            搜索结果列表
        """
        # 生成查询向量
        query_embeddings = self._embed_texts([query])
        query_dense = query_embeddings["dense"][0]
        query_sparse = query_embeddings["sparse"][0]

        # 构建混合搜索请求
        dense_req = AnnSearchRequest(
            data=[query_dense],
            anns_field="content_dense_vector",
            param={"metric_type": "COSINE"},
            limit=limit
        )
        sparse_req = AnnSearchRequest(
            data=[query_sparse],
            anns_field="content_sparse_vector",
            param={"metric_type": "IP"},
            limit=limit
        )

        # 构建过滤条件
        filter_expr = f'project_id == "{project_id}"' if project_id else None

        # 执行混合搜索
        results = await self._client.hybrid_search(
            collection_name=settings.milvus_project_file_collection_name,
            reqs=[dense_req, sparse_req],
            ranker=WeightedRanker(settings.milvus_search_sparse_weight, settings.milvus_search_dense_weight),
            limit=limit,
            filter=filter_expr,
            output_fields=["*"]
        )

        # 格式化结果
        formatted = [
            ProjectFileSearchResult(
                id=hit["id"],
                distance=hit["distance"],
                project_id=hit["entity"].get("project_id", ""),
                name=hit["entity"].get("name", ""),
                path=hit["entity"].get("path", ""),
                type=hit["entity"].get("type", ""),
                content=hit["entity"].get("content", ""),
                summary=hit["entity"].get("summary", ""),
                create_time=hit["entity"].get("create_time", ""),
                metadata=hit["entity"].get("metadata", {})
            )
            for hit in results[0]
        ]

        logger.info(
            f"trans_id:{trans_id_ctx.get()} 方法名:{utils.get_func_name()} 项目Id:{project_id} 返回文件条目:{len(formatted)}")
        return formatted

    async def search_project_context(
            self,
            project_id: str,
            query: str,
            limit: int = 5
    ) -> list[ProjectContextSearchResult]:
        """混合搜索项目对话历史
        
        Args:
            project_id: 项目 ID（必填）
            query: 查询文本
            limit: 返回数量
            
        Returns:
            搜索结果列表
        """
        # 生成查询向量
        query_embeddings = self._embed_texts([query])
        query_dense = query_embeddings["dense"][0]
        query_sparse = query_embeddings["sparse"][0]

        # 构建混合搜索请求
        dense_req = AnnSearchRequest(
            data=[query_dense],
            anns_field="content_dense_vector",
            param={"metric_type": "COSINE"},
            limit=limit
        )
        sparse_req = AnnSearchRequest(
            data=[query_sparse],
            anns_field="content_sparse_vector",
            param={"metric_type": "IP"},
            limit=limit
        )

        # 执行混合搜索
        results = await self._client.hybrid_search(
            collection_name=settings.milvus_project_context_collection_name,
            reqs=[dense_req, sparse_req],
            ranker=WeightedRanker(settings.milvus_search_sparse_weight, settings.milvus_search_dense_weight),
            limit=limit,
            filter=f'project_id == "{project_id}"',
            output_fields=["*"]
        )

        # 格式化结果
        formatted = [
            ProjectContextSearchResult(
                id=hit["id"],
                distance=hit["distance"],
                project_id=hit["entity"].get("project_id", ""),
                content=hit["entity"].get("content", ""),
                create_time=hit["entity"].get("create_time", ""),
                metadata=hit["entity"].get("metadata", {})
            )
            for hit in results[0]
        ]
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 方法名:{utils.get_func_name()} 项目Id:{project_id} 返回上下文条目:{len(formatted)}")
        return formatted

    async def delete_project_file(self, sql_db_id: str) -> None:
        """删除项目文件向量数据
        
        Args:
            sql_db_id: 业务数据库 ID
        """
        await self._client.delete(
            collection_name=settings.milvus_project_file_collection_name,
            filter=f'sql_db_id == "{sql_db_id}"'
        )
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 方法名:{utils.get_func_name()} 文件Id:{sql_db_id} 删除项目文件向量数据")

    async def delete_project(self, project_id: str) -> None:
        """删除项目的所有向量数据
        
        删除项目文件和对话上下文的所有向量数据。
        
        Args:
            project_id: 项目 ID
        """
        # 删除项目文件
        await self._client.delete(
            collection_name=settings.milvus_project_file_collection_name,
            filter=f'project_id == "{project_id}"'
        )
        # 删除项目上下文
        await self._client.delete(
            collection_name=settings.milvus_project_context_collection_name,
            filter=f'project_id == "{project_id}"'
        )
        logger.info(
            f"trans_id:{trans_id_ctx.get()} 方法名:{utils.get_func_name()} 项目Id:{project_id} 删除项目向量数据")

    async def close(self) -> None:
        """关闭连接"""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Milvus 连接已关闭")


# 初始化 MilvusService
milvus_service = MilvusService()
