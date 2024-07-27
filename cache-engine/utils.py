import os
import redis
from redis.commands.search.field import TextField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from sentence_transformers import SentenceTransformer

class RedisManager:
    def __init__(self):
        self.redis_client = None
        self.embedder = None
        self.vector_dimension = int(os.environ['VECTOR_DIMENSION'])

    async def initialize(self):
        self.redis_client = redis.Redis(
            host=os.environ['HOST'],
            port=int(os.environ['PORT']),
            decode_responses=True
        )
        self.embedder = SentenceTransformer(os.environ['EMBEDER'])
        await self.ensure_index()

    async def ensure_index(self):
        index_name = os.environ['INDEX_NAME']
        try:
            self.redis_client.ft(index_name).info()
            print(f"Index '{index_name}' already exists.")
        except redis.ResponseError:
            schema = (
                TextField("$.university_id", no_stem=True, as_name="university_id"),
                TextField("$.query", as_name="query"),
                TextField("$.response", as_name="response"),
                VectorField(
                    "$.query_vector",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.vector_dimension,
                        "DISTANCE_METRIC": "COSINE",
                    },
                    as_name="vector",
                ),
            )
            definition = IndexDefinition(prefix=["cache:"], index_type=IndexType.JSON)
            self.redis_client.ft(index_name).create_index(fields=schema, definition=definition)
            print(f"Index '{index_name}' created successfully.")

    async def close(self):
        if self.redis_client:
            await self.redis_client.close()

redis_manager = RedisManager()