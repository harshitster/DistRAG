import os

class Config:
    DB_HOST = os.environ['POSTGRES_HOST']
    DB_PORT = os.environ['POSTGRES_PORT']
    DB_USER = os.environ['POSTGRES_USER']
    DB_PASSWORD = os.environ['POSTGRES_PASSWORD']
    DB_NAME = os.environ['POSTGRES_DB']