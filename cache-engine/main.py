from fastapi import FastAPI
from utils import redis_manager
from routes import router as cache_router

app = FastAPI()

app.include_router(cache_router)

@app.on_event("startup")
async def startup_event():
    await redis_manager.initialize()

@app.get("/health") 
async def ping():
    return {"server": "healthy and listening requests"}

@app.on_event("shutdown")
async def shutdown_event():
    await redis_manager.close()