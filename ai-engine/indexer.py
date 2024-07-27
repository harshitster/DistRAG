import psycopg2
import pydantic
import sqlalchemy
import json
import time

from collections import deque
from llama_index.core import Document, VectorStoreIndex, Settings
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding

class TableInfo(pydantic.BaseModel):
    table_name: str = pydantic.Field(..., description="table name (must be underscores and NO spaces)")
    table_summary: str = pydantic.Field(..., description="short, concise summary/caption of the table")

class DatabaseIndexer:
    def __init__(self, logger, google_api_keys, llm_model, embedding_model):
        self.logger = logger
        self.google_api_keys = google_api_keys
        self.llm_model = llm_model
        self.embedding_model = embedding_model
            
        self.model_pool = deque(maxlen=len(self.google_api_keys))

        self.load_models()
                
    def load_models(self):
        for api_key in self.google_api_keys:
            self.model_pool.append((
                Gemini(model_name=self.llm_model, api_key=api_key),
                GeminiEmbedding(model_name=self.embedding_model, api_key=api_key)
            ))
                
    def get_next_models(self):
        llm, embedding_model = self.model_pool[0]
        self.model_pool.rotate(-1)
        Settings.llm = llm
        Settings.embed_model = embedding_model
        return llm, embedding_model

    def get_table_info(self, engine, table_name):
        try:
            inspector = sqlalchemy.inspect(engine)
            columns = inspector.get_columns(table_name)
            table_str = f"Columns: "
            for column in columns:
                table_str += f"{column['name']} ({column['type']}), "
            return table_str
        except Exception as e:
            self.logger.error(f"Failed to get table info for {table_name}: {e}")
            raise

    def get_table_summary(self, engine, llm, table_name, exclude_table_name_list):
        try:
            table_str = self.get_table_info(engine, table_name)
            formatted_prompt = self.prompt_str.format(
                exclude_table_name_list=", ".join(exclude_table_name_list),
                table_str=table_str,
                table_name=table_name
            )
            response = llm.complete(formatted_prompt)
            time.sleep(10)
            return response.text
        except Exception as e:
            self.logger.error(f"Failed to get table summary for {table_name}: {e}")
            raise

    def process_tables(self, engine):
        try:
            metadata = sqlalchemy.MetaData()
            metadata.reflect(bind=engine)
            table_names = metadata.tables.keys()

            table_infos = []
            for table_name in table_names:
                llm, _ = self.get_next_models()
                res = False
                while not res:
                    try:
                        summary = self.get_table_summary(engine, llm, table_name, table_names) # skeptical with table names
                        res = True
                    except Exception as e:
                        print("Exception Occured - ", time.time())
                        llm, _ = self.get_next_models()
                try:
                    cleaned_summary = summary.strip().lstrip('`').rstrip('`')
                    if cleaned_summary.startswith('json'):
                        cleaned_summary = cleaned_summary[4:].strip()
                    result = json.loads(cleaned_summary)
                    table_summary = result['table_summary']
                except json.JSONDecodeError:
                    table_summary = summary

                table_info = TableInfo(table_name=table_name, table_summary=table_summary)
                table_infos.append(table_info)

            self.logger.info(f"Processed {len(table_infos)} tables")
            return table_infos
        except Exception as e:
            self.logger.error(f"Failed to process tables: {e}")
            raise

    def create_documents(self, table_infos):
        try:
            documents = []
            for table_info in table_infos:
                content = f"Table Name: {table_info.table_name}\nTable Summary: {table_info.table_summary}"
                doc = Document(text=content, metadata={"table_name": table_info.table_name})
                documents.append(doc)
            self.logger.info(f"Created {len(documents)} documents")
            return documents
        except Exception as e:
            self.logger.error(f"Failed to create documents: {e}")
            raise

    def create_index(self, documents, storage_context):
        try:
            index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)
            self.logger.info("Vector index created successfully")
            return index
        except Exception as e:
            self.logger.error(f"Failed to create vector index: {e}")
            raise

    prompt_str = """
        Given the following table information, provide a brief, general summary of what kind of data this table might contain. 
        Output should be in the form of a JSON string: {{"table_name": "<suggested_name>", "table_summary": "<brief_summary>"}}
        The table name should be descriptive but generic, avoiding any specific identifiers.
        Do NOT use any of the following names: {exclude_table_name_list}
        Table information: {table_str}
    """

    def run(self, engine, storage_context):
        try:
            table_infos = self.process_tables(engine)
            documents = self.create_documents(table_infos)
            index = self.create_index(documents, storage_context)
            self.logger.info("Indexing process completed successfully")
            return index
        except Exception as e:
            self.logger.error(f"Indexing process failed: {e}")
            raise