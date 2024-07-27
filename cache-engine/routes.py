import json
import time
import numpy as np
import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from redis.commands.search.query import Query
from utils import redis_manager

router = APIRouter()

class QueryRequest(BaseModel):
    input_str: str
    university_id: str

class CacheRequest(BaseModel):
    university_id: str
    query: str
    response: str
    version: str

MAX_CACHE_SIZE_PER_UNIVERSITY = int(os.environ['MAX_CACHE_PER'])
CACHE_EVICTION_ALGORITHM = os.environ['CACHE_ALGO']

async def get_redis_client():
    return redis_manager.redis_client

@router.post("/cache_response")
async def cache_response(request: CacheRequest, redis_client = Depends(get_redis_client)):
    try:
        pipeline = redis_client.pipeline()

        encoded_query = redis_manager.embedder.encode(request.query).astype(np.float32).tolist()
        cache_key = f"cache:{request.university_id}"

        cache_size = redis_client.zcard(cache_key)
        if cache_size >= MAX_CACHE_SIZE_PER_UNIVERSITY:
            if CACHE_EVICTION_ALGORITHM == "LFU":
                least_used = redis_client.zrange(cache_key, 0, 0)[0]
                pipeline.zrem(cache_key, least_used)
            else: 
                oldest = redis_client.zrange(cache_key, 0, 0, withscores=True)[0]
                pipeline.zremrangebyscore(cache_key, oldest[1], oldest[1])

        data = {
            "query": request.query,
            "query_vector": encoded_query,
            "response": json.dumps(request.response),
        }
        score = time.time() if CACHE_EVICTION_ALGORITHM == "ROUND_ROBIN" else 1
        pipeline.zadd(cache_key, {json.dumps(data): score})

        if CACHE_EVICTION_ALGORITHM == "LFU":
            pipeline.zincrby(cache_key, 1, json.dumps(data))

        pipeline.execute()
        
        return True
    except Exception as e:
        print(f"Error in cache_response: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error caching response: {str(e)}")
    
@router.post("/get_cached_response")
async def get_cached_response(query: QueryRequest, redis_client=Depends(get_redis_client)):
    try:
        encoded_query = redis_manager.embedder.encode(query.input_str)
        cache_key = f"cache:{query.university_id}"

        cached_items = redis_client.zrange(cache_key, 0, -1)
        
        if len(cached_items) == 0:
            return None

        results = []
        for item in cached_items:
            item_data = json.loads(item)
            similarity = np.dot(encoded_query, item_data['query_vector']) / (np.linalg.norm(encoded_query) * np.linalg.norm(item_data['query_vector']))
            results.append((similarity, item_data))

        results.sort(key=lambda x: x[0], reverse=True)
        top_results = results[:3]

        if CACHE_EVICTION_ALGORITHM == "LFU":
            for _, item_data in top_results:
                redis_client.zincrby(cache_key, 1, json.dumps(item_data))

        return [{"query": item['query'], "response": json.loads(item['response']), "similarity": sim} for sim, item in top_results]

    except Exception as e:
        print(f"Error in get_cached_response: {str(e)}")
        print(f"Exception type: {type(e)}")
        print(f"Exception args: {e.args}")
        raise HTTPException(status_code=500, detail=f"Error searching cache: {str(e)}")

@router.post("/flush_all_data")
async def flush_all_data(redis_client=Depends(get_redis_client)):
    try:
        redis_client.flushall()
        
        await redis_manager.ensure_index()
        
        return {"status": "All data flushed successfully"}
    except Exception as e:
        print(f"Error in flush_all_data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error flushing data: {str(e)}")