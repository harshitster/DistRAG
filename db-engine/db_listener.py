import psycopg2
import psycopg2.extensions
import select
import os
import logging

class DatabaseChangeListener:
    def __init__(self, config, callback):
        self.config = config
        self.callback = callback
        self.running = True

        self.store_path = os.path.join(os.getcwd(), 'db-store')

        self.setup_logger()

    def setup_logger(self):
        logger = logging.getLogger('db_listener')
        logger.setLevel(logging.DEBUG)
        
        os.makedirs(self.store_path, exist_ok=True)
        
        file_handler = logging.FileHandler(os.path.join(self.store_path, 'db_listener.log'), mode='w')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)

        logger.propagate = False
        
        self.logger = logger

    def listen(self):
        try:
            conn = psycopg2.connect(
                user=self.config.DB_USER,
                password=self.config.DB_PASSWORD,
                host=self.config.DB_HOST,
                port=self.config.DB_PORT,
                dbname=self.config.DB_NAME
            )
        except:
            self.logger.error('Connection to Database - Unsuccessful')
            raise

        self.logger.info('Connection to Database - Successful')

        conn.set_isolation_level(
            psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT
        )

        cur = conn.cursor()
        cur.execute("LISTEN db_changes;")

        self.logger.info("Listening for Database Changes...")

        while self.running:
            if select.select([conn], [], [], 5) != ([], [], []):
                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    self.logger.info(f"Got NOTIFY: {notify.pid}, {notify.channel}, {notify.payload}")
                    self.callback()

        cur.close()
        conn.close()

    def stop(self):
        self.running = False