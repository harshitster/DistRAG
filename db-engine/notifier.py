import asyncio
import os
import httpx
import logging
from change_listener import ChangeListener

class Notifier:
    def __init__(self):
        self.listener = ChangeListener(self.notify_cache_engine, self.notify_llm_servers_cache_engine)
        self.cache_engine_endpoint = os.environ['CACHE_ENGINE_ENDPOINT']
        self.llm_endpoints = os.environ['LLM_ENDPOINTS'].split(',')

        self.log_path = os.path.join('/app/db-store')
        self.setup_logger()

    def setup_logger(self):
        os.makedirs(self.log_path, exist_ok=True)
        logging.basicConfig(
            filename=os.path.join(self.log_path, 'cache-notifier.log'),
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filemode='w'
        )

    async def notify_cache_engine(self, university_id):
        logging.info(f"Data update notification received for university with id: {university_id}")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{self.cache_engine_endpoint}/flush_university_cache", json={"university_id": university_id})
                if response.status_code == 200:
                    logging.info(f"Successfully notified cache-engine to flush data for university_id: {university_id}")
                else:
                    logging.error(f"Failed to notify cache-engine about {university_id}. Status code: {response.status_code}")
            except Exception as e:
                logging.error(f"Error notifying cache-engine: {str(e)}")
                raise

    async def notify_llm_servers_cache_engine(self):
        async with httpx.AsyncClient() as client:
            tasks = [self.notify_llm_server(client, server) for server in self.llm_endpoints]
            await asyncio.gather(*tasks)

            try:
                response = await client.post(f"{self.cache_engine_endpoint}/flush_all_data")
                if response.status_code == 200:
                    logging.info(f"Successfully notified cache-engine to flush all data.")
                else:
                    logging.error(f"Failed to notify cache-engine. Status code: {response.status_code}")
            except Exception as e:
                logging.error(f"Error notifying cache-engine: {str(e)}")
                raise

    async def notify_llm_server(self, client, server):
        try:
            response = await client.post(f"{server}/rebuild")
            if response.status_code == 200:
                logging.info(f"Successfully notified {server}")
            else:
                logging.error(f"Failed to notify {server}. Status: {response.status_code}")
        except Exception as e:
            logging.error(f"Error notifying {server}: {str(e)}")
            raise

    async def run_async(self):
        await self.listener.listen()

    def run(self):
        asyncio.run(self.run_async())