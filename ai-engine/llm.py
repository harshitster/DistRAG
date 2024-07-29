import os
import logging
import threading
import time
import sqlalchemy
import chromadb # type: ignore
import queue
from collections import deque
from contextlib import ExitStack
from llama_index.llms.gemini import Gemini # type: ignore
from llama_index.core import Settings, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore # type: ignore

import indexer
import pipeline

class LLM:
    def __init__(self):
        self.store_path = os.path.join(os.getcwd(), 'llm-store')
        if not os.path.exists(self.store_path):
            os.makedirs(self.store_path)

        self.setup_logger()
        self.load_environment_variables()

        self.running = True
        self.query_queue = queue.Queue()
        self.rebuild_queue = queue.Queue()

        self.llm_pool = deque(maxlen=len(self.google_api_keys))
        self.pipeline_pool = deque(maxlen=len(self.google_api_keys))
        self.qb_locks = []
        self.version = 0

        self.last_rebuild_time = 0
        self.rebuild_interval = 60

        self.setup()

        self.query_thread = threading.Thread(target=self.process_queries)
        self.listen_rebuild_thread = threading.Thread(target=self.listen_rebuild)
        self.query_thread.start()
        self.listen_rebuild_thread.start()

    def setup_logger(self):
        logger = logging.getLogger('run_llm')
        logger.setLevel(logging.DEBUG)
        
        os.makedirs(self.store_path, exist_ok=True)
        
        file_handler = logging.FileHandler(os.path.join(self.store_path, 'run_llm.log'), mode='w')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.propagate = False
        
        self.logger = logger

    def load_environment_variables(self):
        try:
            self.host = os.environ['POSTGRES_HOST']
            self.port = os.environ['POSTGRES_PORT']
            self.user = os.environ['POSTGRES_USER']
            self.password = os.environ['POSTGRES_PASSWORD']
            self.dbname = os.environ['POSTGRES_DB']

            self.google_api_keys = os.environ['GOOGLE_API_KEYS'].strip().split('\n')
            self.llm_model = os.environ['LLM_MODEL']
            self.embedding_model = os.environ['EMBED_MODEL']

            self.logger.info("Environment Variables Loaded.")
        except AttributeError as e:
            self.logger.error(f"Configuration error: {e}")
            raise

    def database_connection(self):
        try:
            db_connection_string = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"
            engine = sqlalchemy.create_engine(db_connection_string)
            self.logger.info("SQLAlchemy Database Connection Established")
            return engine
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {e}")
            raise

    def load_llms(self):
        try:
            for api_key in self.google_api_keys:
                self.llm_pool.append(Gemini(model_name=self.llm_model, api_key=api_key))
            self.logger.info("LLM and Embedding models set up")
        except Exception as e:
            self.logger.error(f"Failed to set up LLM or embedding model: {e}")
            raise

    def get_next_llm(self):
        llm = self.llm_pool[0]
        self.llm_pool.rotate(-1)
        return llm

    def chroma(self):
        try:
            client = chromadb.PersistentClient(path=os.path.join(self.store_path, "chroma_db"))
            chroma_collection = client.get_or_create_collection("table_info_collection")
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            self.logger.info("Chroma set up successfully")
            return client, chroma_collection, vector_store, storage_context
        except Exception as e:
            self.logger.error(f"Failed to set up Chroma: {e}")
            raise

    def setup(self):
        self.engine = self.database_connection()
        self.load_llms()
        self.client, self.chroma_collection, self.vector_store, self.storage_context = self.chroma()
        self.database_indexer = indexer.DatabaseIndexer(self.logger, self.google_api_keys, self.llm_model, self.embedding_model)
        self.create_index_and_pipelines()

    def create_index_and_pipelines(self):
        index = self.database_indexer.run(self.engine, self.storage_context)
        for _ in range(self.pipeline_pool.maxlen):
            llm = self.get_next_llm()
            query_pipeline = pipeline._build_query_pipeline(self.engine, self.vector_store, llm)
            qb_lock = threading.Lock()
            self.pipeline_pool.append((query_pipeline, llm, qb_lock))
            self.qb_locks.append(qb_lock)
        self.logger.info(f"Created pipeline pool with {len(self.pipeline_pool)} pipelines")

    def get_next_pipeline(self):
        query_pipeline, llm, qb_lock = self.pipeline_pool[0]
        Settings.llm = llm
        self.pipeline_pool.rotate(-1)
        return query_pipeline, llm, qb_lock

    def rebuild_index_and_pipeline(self):
        self.logger.info("Rebuilding index and query pipeline pool")
        new_pipeline_pool = deque(maxlen=self.pipeline_pool.maxlen)

        index = self.database_indexer.run(self.engine, self.storage_context)
        for i in range(self.pipeline_pool.maxlen):
            _, llm, qb_lock = self.get_next_pipeline()
            Settings.llm = llm
            query_pipeline = pipeline._build_query_pipeline(self.engine, self.vector_store, llm)
            new_pipeline_pool.append((query_pipeline, llm, qb_lock))

        self.pipeline_pool = new_pipeline_pool
        self.logger.info("Rebuild complete. New pipeline pool created.")

    def trigger_rebuild(self):
        try:
            self.rebuild_queue.put_nowait(time.time())
            self.logger.info("Database change detected. Rebuild queued.")
        except queue.Full:
            self.logger.warning("Rebuild queue is full. Skipping this rebuild trigger.")

    def listen_rebuild(self):
        while self.running:
            try:
                rebuild_time = self.rebuild_queue.get(timeout=1)
                current_time = time.time()
                
                if current_time - self.last_rebuild_time >= self.rebuild_interval:
                    with ExitStack() as stack:
                        for lock in self.qb_locks:
                            stack.enter_context(lock)
                        
                        self.rebuild_index_and_pipeline()
                        self.last_rebuild_time = current_time
                        
                        while not self.rebuild_queue.empty():
                            self.rebuild_queue.get_nowait()
                    
                    self.version += 1
                else:
                    self.rebuild_queue.put(rebuild_time)
            except queue.Empty:
                pass 
            except Exception as e:
                self.logger.error(f"An error occurred in rebuild thread: {e}")

    def query(self, query_text):
        future = threading.Event()
        result = []
        self.query_queue.put((query_text, future, result))
        future.wait()
        return result[0]

    def process_queries(self):
        while self.running:
            query_text, event, result = self.query_queue.get()
            if query_text is None:
                break

            query_pipeline, llm, qb_lock = self.get_next_pipeline()
            Settings.llm = llm
            
            with qb_lock:
                response = str(query_pipeline.run(query=query_text))

            current_version = self.version
            result.append((response, current_version))
            event.set()

    def stop(self):
        self.running = False
        self.query_queue.put((None, None, None))
        self.listen_rebuild_thread.join()
        self.query_thread.join()
        self.logger.info("RunLLM has stopped.")