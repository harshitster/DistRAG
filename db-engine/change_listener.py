import psycopg2 # type: ignore
import psycopg2.extensions # type: ignore
import select
import os
import logging
import json
import asyncio

class ChangeListener:
    def __init__(self, write_callback, schema_callback):
        self.write_callback = write_callback
        self.schema_callback = schema_callback
        self.running = True

        self.log_path = os.path.join('/app/db-store')
        self.setup_logger()

        self.host = os.environ['POSTGRES_HOST']
        self.port = os.environ['POSTGRES_PORT']
        self.user = os.environ['POSTGRES_USER']
        self.password = os.environ['POSTGRES_PASSWORD']
        self.dbname = os.environ['POSTGRES_DB']

    def setup_logger(self):
        os.makedirs(self.log_path, exist_ok=True)
        logging.basicConfig(
            filename=os.path.join(self.log_path, 'db-schema-change.log'),
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filemode='w'
        )

    async def listen(self):
        try:
            conn = psycopg2.connect(
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                dbname=self.dbname
            )
        except psycopg2.Error as e:
            logging.error(f'Connection to Database - Unsuccessful: {e}')
            raise

        logging.info("Connection to Database - Successful")
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        cur.execute("LISTEN data_changes;")
        cur.execute("LISTEN schema_changes;")
        logging.info("Listening for Data and Schema Changes...")

        while self.running:
            if select.select([conn], [], [], 5) != ([], [], []):
                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    logging.info(f"Got NOTIFY: {notify.pid}, {notify.channel}, {notify.payload}")
                    try:
                        payload = json.loads(notify.payload)
                        if notify.channel == 'data_changes':
                            university_id = payload.get('university_id')
                            if university_id:
                                await self.write_callback(university_id)
                        elif notify.channel == 'schema_changes':
                            await self.schema_callback()
                    except json.JSONDecodeError:
                        logging.error(f"Invalid JSON payload: {notify.payload}")
            await asyncio.sleep(0) 

        cur.close()
        conn.close()