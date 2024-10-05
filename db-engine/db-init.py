import os
import psycopg2 # type: ignore
import logging
from psycopg2.extras import DictCursor # type: ignore

# Set up logging
dir_path = os.path.join('/app/db-store')
os.makedirs(dir_path, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(dir_path, 'db-init.log'),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)

# Database connection parameters
host = os.environ['POSTGRES_HOST']
port = int(os.environ['POSTGRES_PORT'])
user = os.environ['POSTGRES_USER']
password = os.environ['POSTGRES_PASSWORD']
dbname = os.environ['POSTGRES_DB']

logging.info(f"Connecting to host: {host}, port: {port}, user: {user}, dbname: {dbname}")

def split_sql_commands(sql_content):
    commands = []
    current_command = []
    in_function = False
    for line in sql_content.split('\n'):
        stripped_line = line.strip()
        if stripped_line.startswith('CREATE OR REPLACE FUNCTION') or stripped_line.startswith('CREATE FUNCTION'):
            in_function = True
        current_command.append(line)
        if in_function:
            if stripped_line.endswith('LANGUAGE plpgsql;'):
                commands.append('\n'.join(current_command))
                current_command = []
                in_function = False
        elif stripped_line.endswith(';') and not in_function:
            commands.append('\n'.join(current_command))
            current_command = []
    if current_command:
        commands.append('\n'.join(current_command))
    return commands

def execute_sql_file(cursor, filename):
    with open(filename, 'r') as file:
        content = file.read()
    logging.debug(f"Content of {filename}:\n{content}")
    commands = split_sql_commands(content)
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

try:
    # Establish database connection
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname
    )
    logging.info("Connection - Successful")

    with conn.cursor() as cur:
        # Execute schema_and_triggers.sql
        logging.info("Executing schema.sql")
        execute_sql_file(cur, 'schema.sql')
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