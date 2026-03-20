import os
import subprocess
import time
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ReloadHandler(FileSystemEventHandler):
    def __init__(self, process):
        self.process = process

    def on_modified(self, event):
        if event.src_path.endswith('.py') or event.src_path.endswith('.html'):
            print(f"File modified: {event.src_path}. Reloading...")
            # No need to manually restart runserver as it has its own watcher,
            # but we can add browser-sync trigger here if needed.

def run_dev_server():
    print("Starting Django Dev Server in Background...")
    # Run the server in a way that doesn't block this script
    cmd = [sys.executable, "manage.py", "runserver", "0.0.0.0:8001"]
    process = subprocess.Popen(cmd)
    
    try:
        while True:
            time.sleep(1)
            if process.poll() is not None:
                print("Server stopped. Restarting...")
                process = subprocess.Popen(cmd)
    except KeyboardInterrupt:
        process.terminate()
        print("Stopping dev server.")

if __name__ == "__main__":
    run_dev_server()
