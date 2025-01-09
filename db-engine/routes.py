from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import psycopg2
from typing import Dict, Any
import os

router = APIRouter()

DB_CONFIG = {
    "host": os.environ['POSTGRES_HOST'],
    "port": os.environ['POSTGRES_PORT'],
    "user": os.environ['POSTGRES_USER'],
    "password": os.environ['POSTGRES_PASSWORD'],
    "dbname": os.environ['POSTGRES_DB']
}

class InsertRequest(BaseModel):
    table_name: str
    university_id: str
    data: Dict[str, Any]

class UpdateRequest(BaseModel):
    table_name: str
    university_id: str
    data: Dict[str, Any]
    where_clause: Dict[str, Any]

class DeleteRequest(BaseModel):
    table_name: str
    university_id: str
    where_clause: Dict[str, Any]

class DatabaseOperations:
    @staticmethod
    def execute_with_notifications(sql, params, university_id, table_name, operation):
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(sql, params)
                    cur.execute(
                        "SELECT notify_change(%s, %s, %s)",
                        (university_id, table_name, operation)
                    )
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    raise HTTPException(status_code=500, detail=str(e))
                
@router.post("/insert")
async def insert_data(request: InsertRequest):
    columns = list(request.data.keys())
    values = list(request.data.values())
    placeholders = ["%s"] * len(values)
    
    sql = f"""
        INSERT INTO {request.table_name} 
        ({', '.join(columns)}) 
        VALUES ({', '.join(placeholders)})
    """
    
    DatabaseOperations.execute_with_notification(
        sql=sql,
        params=tuple(values),
        university_id=request.university_id,
        table_name=request.table_name,
        operation="INSERT"
    )
    
    return {"status": "success", "message": "Data inserted successfully"}

@router.post("/update")
async def update_data(request: UpdateRequest):
    set_items = [f"{k} = %s" for k in request.data.keys()]
    where_items = [f"{k} = %s" for k in request.where_clause.keys()]
    
    sql = f"""
        UPDATE {request.table_name}
        SET {', '.join(set_items)}
        WHERE {' AND '.join(where_items)}
    """
    
    params = tuple(list(request.data.values()) + list(request.where_clause.values()))
    
    DatabaseOperations.execute_with_notification(
        sql=sql,
        params=params,
        university_id=request.university_id,
        table_name=request.table_name,
        operation="UPDATE"
    )
    
    return {"status": "success", "message": "Data updated successfully"}

@router.post("/delete")
async def delete_data(request: DeleteRequest):
    where_items = [f"{k} = %s" for k in request.where_clause.keys()]
    
    sql = f"""
        DELETE FROM {request.table_name}
        WHERE {' AND '.join(where_items)}
    """
    
    DatabaseOperations.execute_with_notification(
        sql=sql,
        params=tuple(request.where_clause.values()),
        university_id=request.university_id,
        table_name=request.table_name,
        operation="DELETE"
    )
    
    return {"status": "success", "message": "Data deleted successfully"}