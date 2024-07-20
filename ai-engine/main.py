import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from llm import LLM

app = FastAPI()
llm_instance = LLM()

class QueryRequest(BaseModel):
    input_str: str

@app.post("/query")
def query(query: QueryRequest):
    try:
        response, version = llm_instance.query(query.input_str)
        return {"response": response, "version": version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "healthy", "llm_id": os.environ['LLM_ID']}

@app.post("/rebuild")
def rebuild():
    llm_instance.trigger_rebuild()
    return {"status": "rebuild initiated"}

@app.on_event("shutdown")
def shutdown_event():
    llm_instance.stop()