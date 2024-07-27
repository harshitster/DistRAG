import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from llm import LLM
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
llm_instance = LLM()

CACHE_ENGINE_URL = os.environ['CACHE_ENGINE_URL']
logger.info(f"CACHE_ENGINE_URL: {CACHE_ENGINE_URL}")

class QueryRequest(BaseModel):
    input_str: str
    university_id: str

class CacheRequest(BaseModel):
    university_id: str
    query: str
    response: str
    version: str

async def get_cached_response(query: QueryRequest):
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Attempting to get cached response from: {CACHE_ENGINE_URL}/get_cached_response")
            response = await client.post(f"{CACHE_ENGINE_URL}/get_cached_response", json=query.dict())
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Cache engine error: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {e}")
            raise HTTPException(status_code=503, detail=f"Cache service unavailable: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error while fetching cached response: {str(e)}")

async def cache_response(university_id: str, query: str, response: str, version: int):
    cache_request = CacheRequest(
        university_id=university_id,
        query=query,
        response=response,
        version=str(version)
    )
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{CACHE_ENGINE_URL}/cache_response", json=cache_request.dict())
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to cache response: HTTP {e.response.status_code}")
            logger.error(f"Response content: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Cache service unavailable while caching: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while caching response: {str(e)}")

@app.post("/query")
async def query(query: QueryRequest):
    try:
        logger.info("Checking for Cache...")
        cached_response = await get_cached_response(query)
        
        if cached_response:
            logger.info("Cache hit!")
            return {"response": cached_response[0]["response"], "version": "cached", "source": "cache"}
        
        logger.info("Cache miss. Getting response from ai-engine...")
        response, version = llm_instance.query(query.input_str)
        
        logger.info("Caching the response...")
        await cache_response(query.university_id, query.input_str, response, version)
        
        return {"response": response, "version": str(version), "source": "llm"}
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
    
@app.get("/")
def health_check():
    return {"status": "healthy", "llm_id": os.environ['LLM_ID']}

@app.post("/rebuild")
async def rebuild():
    try:
        async with httpx.AsyncClient() as client:
            flush_response = await client.post(f"{CACHE_ENGINE_URL}/flush_all_data")
            flush_response.raise_for_status()
            logger.info("Cache data flushed successfully")

        llm_instance.trigger_rebuild()
        logger.info("LLM rebuild initiated")

        return {"status": "Cache flushed and rebuild initiated"}
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred while flushing cache: {e}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Error flushing cache: {e.response.text}")
    except Exception as e:
        logger.error(f"Error during rebuild process: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error during rebuild process: {str(e)}")
@app.on_event("shutdown")
def shutdown_event():
    llm_instance.stop()