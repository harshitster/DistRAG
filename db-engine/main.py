import threading
import uvicorn
from fastapi import FastAPI
import os
from routes import router
from notifier import Notifier

app = FastAPI(title="Database Operations API")

app.include_router(router, prefix="")

def run_notifier():
    change_notifier = Notifier()
    change_notifier.run()

def run_api():
    port = int(os.environ['UVICORN_PORT'])
    uvicorn.run(app, host="0.0.0.0", port=port)

def main():
    notifier_thread = threading.Thread(target=run_notifier)
    notifier_thread.daemon = True
    notifier_thread.start()

    run_api()

if __name__ == "__main__":
    main()