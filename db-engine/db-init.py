import os
import psycopg2 
import logging
from psycopg2.extras import DictCursor 

class DBInit:
    def __init__(self):
        self.setup_logging()

    def setup_logging(self):
        dir_path = os.path.join('/app/db-store')
        os.makedirs(dir_path, exist_ok=True)
        
        logging.basicConfig(
            filename=os.path.join(dir_path, 'db-init.log'),
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filemode='w'
        )

    def split_sql_commands(self, sql_content):
        commands = []
        current_command = []
        in_function = False
        in_trigger = False
        
        for line in sql_content.split('\n'):
            stripped_line = line.strip()
            
            if stripped_line.startswith('CREATE OR REPLACE FUNCTION') or stripped_line.startswith('CREATE FUNCTION'):
                in_function = True
                
            elif stripped_line.startswith('CREATE EVENT TRIGGER'):
                in_trigger = True
                
            current_command.append(line)
            
            if in_function and stripped_line.endswith('LANGUAGE plpgsql;'):
                commands.append('\n'.join(current_command))
                current_command = []
                in_function = False
                
            elif in_trigger and stripped_line.endswith('notify_schema_change();'):
                commands.append('\n'.join(current_command))
                current_command = []
                in_trigger = False
                
            elif not in_function and not in_trigger and stripped_line.endswith(';'):
                commands.append('\n'.join(current_command))
                current_command = []
                
        if current_command:
            commands.append('\n'.join(current_command))
            
        return commands
    
    def execute_sql_file(self, cursor, filename):
        with open(filename, 'r') as file:
            content = file.read()

        logging.debug(f"Content of {filename}:\n{content}")
        commands = self.split_sql_commands(content)

        for command in commands:
            command = command.strip()
            if command:
                logging.debug(f"Executing command:\n{command}")
                try:
                    cursor.execute(command)
                    logging.info(f"Command executed successfully")
                except psycopg2.Error as e:
                    logging.error(f"Error executing command: {e}")
                    raise

    def run(self):
        host = os.environ['POSTGRES_HOST']
        port = int(os.environ['POSTGRES_PORT'])
        user = os.environ['POSTGRES_USER']
        password = os.environ['POSTGRES_PASSWORD']
        dbname = os.environ['POSTGRES_DB']

        logging.info(f"Connecting to host: {host}, port: {port}, user: {user}, dbname: {dbname}")
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                dbname=dbname
            )
            logging.info("Connection - Successful")

            with conn.cursor() as cur:
                logging.info("Executing schema.sql")
                self.execute_sql_file(cur, 'schema.sql')
                logging.info("Schema implementation completed")

            conn.commit()
            logging.info("Database Established Successfully")
        except psycopg2.Error as e:
            logging.error(f"PostgreSQL error: {e}")
            if 'conn' in locals():
                conn.rollback()
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
        finally:
            if 'conn' in locals() and conn is not None:
                conn.close()
            logging.info("Connection Closed")

if __name__ == "__main__":
    dbinit = DBInit()
    dbinit.run()