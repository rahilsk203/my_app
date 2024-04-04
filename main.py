import subprocess
import time
import sys
import os
import psutil
import threading
import keyboard

from flask import Flask, request, jsonify
from flask_cors import CORS
from PeakPxApi import PeakPx
import json
from gunicorn.app.base import BaseApplication

app = Flask(__name__)
CORS(app)
px = PeakPx()

# Server key
server_key = "wallartify2024new"

def validate_key(request):
    client_sent_key = request.args.get('key')
    return client_sent_key == server_key

def search_wallpapers(query):
    wallpapers = px.search_wallpapers(query=query)
    if wallpapers:
        # Extract image URLs from the wallpapers list
        image_urls = [wallpaper['url'] for wallpaper in wallpapers]
        return image_urls
    else:
        return []

@app.route('/search_wallpapers', methods=['GET'])
def search_wallpapers_route():
    if not validate_key(request):
        return jsonify({'error': 'Invalid client key'}), 401

    query = request.args.get('query')

    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400
    
    image_urls = search_wallpapers(query)
    if image_urls:
        # Create a list of dictionaries where each dictionary contains 'Image' key and image URL as value
        response_data = [{'Image': url} for url in image_urls]
        
        # Send JSON response containing the list of image URLs
        return jsonify(response_data), 200
    else:
        return jsonify({'error': 'No wallpapers found for the given query'}), 404

class StandaloneApplication(BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {key: value for key, value in self.options.items() if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application

def run_flask_app():
    subprocess.Popen(["playit"])  # Start playit with default settings
    subprocess.run(["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--preload", "--threads", "2", "main:app"])

def schedule_reboot():
    while True:
        time.sleep(3600)  # Sleep for 1 hour (3600 seconds)
        subprocess.run(["reboot"])

def monitor_memory():
    threshold = 90
    memory_usage = psutil.virtual_memory().percent
    return memory_usage > threshold

def kill_flask_server():
    try:
        pid = None
        for proc in psutil.process_iter():
            if proc.name() == "gunicorn" and "--bind" in proc.cmdline() and "main:app" in proc.cmdline():
                pid = proc.pid
                break
        if pid:
            os.kill(pid, signal.SIGINT)
    except Exception as e:
        print("Error occurred while killing Flask server:", str(e), file=sys.stderr)

def run_flask_in_thread():
    thread = threading.Thread(target=run_flask_app)
    thread.start()
    time.sleep(7)  # Sleep for 7 seconds
    kill_flask_server()  # Terminate the Flask server process

if __name__ == "__main__":
    while True:
        try:
            run_flask_in_thread()
            time.sleep(1)  # Ensure the script has time to exit before restarting
            subprocess.run(["python3", "main.py"])  # Start a new instance of the script
        except Exception as e:
            print("An error occurred:", str(e), file=sys.stderr)
            continue
