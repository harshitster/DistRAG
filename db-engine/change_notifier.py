import asyncio
import aiohttp
from db_listener import DatabaseChangeListener
from config import Config

class DBChangeNotifier:
    def __init__(self, config):
        self.config = config
        self.db_listener = DatabaseChangeListener(config, self.notify_llm_servers)
        self.llm_servers = ["http://llm1:8000", "http://llm2:8000", "http://llm3:8000"]

    async def notify_llm_servers(self):
        async with aiohttp.ClientSession() as session:
            tasks = [self.notify_server(session, server) for server in self.llm_servers]
            await asyncio.gather(*tasks)

    async def notify_server(self, session, server):
        try:
            async with session.post(f"{server}/rebuild") as response:
                if response.status == 200:
                    print(f"Successfully notified {server}")
                else:
                    print(f"Failed to notify {server}. Status: {response.status}")
        except Exception as e:
            print(f"Error notifying {server}: {str(e)}")

    def run(self):
        self.db_listener.listen()

if __name__ == "__main__":
    config = Config()
    notifier = DBChangeNotifier(config)
    notifier.run()