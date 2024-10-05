import json
import time
import yaml
from collections import deque
from llama_index.core import Document, VectorStoreIndex, Settings
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding

class UniMap:
    def __init__(self, config_file='unimap_config.yml', api_file='unimap_api.yml'):        
        self.load_config(config_file, api_file)
        
        self.current_llm = None
        self.current_embedding_model = None
        self.load_next_model()
        
        self.index = self.create_index()

    def load_config(self, config_file, api_file):
        with open(config_file, 'r') as file:
            config = yaml.safe_load(file)
        with open(api_file, 'r') as file:
            api_keys = yaml.safe_load(file)

        self.google_api_keys = deque(api_keys['google_api_keys'])
        self.hashmap = config['universities']
        self.llm_model = config['llm_model']
        self.embedding_model = config['embedding_model']

    def load_next_model(self):
        if not self.google_api_keys:
            raise ValueError("No more API keys available")
        
        api_key = self.google_api_keys.popleft()
        self.current_llm = Gemini(model_name=self.llm_model, api_key=api_key)
        self.current_embedding_model = GeminiEmbedding(model_name=self.embedding_model, api_key=api_key)
        
        Settings.llm = self.current_llm
        Settings.embed_model = self.current_embedding_model
        
        print("New Model Loaded")
        self.google_api_keys.append(api_key) 

    def create_documents(self):
        documents = []
        for uni_name, uni_id in self.hashmap.items():
            content = f"University Name: {uni_name}\nUniversity ID: {uni_id}"
            doc = Document(text=content, metadata={"university_name": uni_name, "university_id": uni_id})
            documents.append(doc)
        return documents

    def retry_with_timeout(self, operation, *args, **kwargs):
        start_time = time.time()
        timeout = 120  # 2 minutes

        while time.time() - start_time < timeout:
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                print(f"Exception occurred: {str(e)}")
                self.load_next_model() 
                time.sleep(1)  

        raise TimeoutError("Operation timed out after 2 minutes of retries")

    def create_index(self):
        def _create_index():
            documents = self.create_documents()
            return VectorStoreIndex.from_documents(documents)

        return self.retry_with_timeout(_create_index)

    def extract_university(self, query):
        def _extract_university():
            response = self.current_llm.complete(
                f"Extract the university name from this query, if any: '{query}'. "
                "If no specific university is mentioned, say 'None'."
            )
            return response.text.strip()

        return self.retry_with_timeout(_extract_university)
    
    def get_university_name(self, university_id):
        for name, id in self.hashmap.items():
            if id == university_id:
                return name
        return "Unknown University"

    def process_query(self, query):
        def _process_query():
            university_name = self.extract_university(query)
            
            if university_name.lower() == 'none':
                return '$'
            else:
                query_engine = self.index.as_query_engine()
                response = query_engine.query(
                    f"Find the university ID for {university_name}. "
                    "Your response should must only include the university ID and strictly nothing more."
                )
                
                try:
                    response_text = response.response
                    university_id = response_text.strip()
                    return university_id
                except Exception:
                    return self.hashmap.get(university_name, '$')

        return self.retry_with_timeout(_process_query)