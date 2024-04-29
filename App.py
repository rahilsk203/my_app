import subprocess
import time
import csv
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from PeakPxApi import PeakPx
from gunicorn.app.base import BaseApplication

app = Flask(__name__)
CORS(app)
px = PeakPx()

# Server key
server_key = "wallartify2024new"

# Setup CSV file for logging queries
def setup_csv():
    if not os.path.exists('ip_query_log.csv'):
        with open('ip_query_log.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["ID", "IP Address", "Query", "Timestamp"])

# Log query to CSV
def log_query(ip_address, query):
    with open('ip_query_log.csv', 'a', newline='') as file:
        writer = csv.writer(file)
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        # You might want to implement a system to generate unique IDs
        writer.writerow([ip_address, query, timestamp])

# Validate client key
def validate_key(request):
    client_sent_key = request.args.get('key')
    return client_sent_key == server_key

# Search wallpapers using PeakPx API
def search_wallpapers(query):
    wallpapers = px.search_wallpapers(query=query)
    if wallpapers:
        image_urls = [wallpaper['url'] for wallpaper in wallpapers]
        return image_urls
    else:
        return []

# API endpoint to search wallpapers
@app.route('/search_wallpapers', methods=['GET'])
def search_wallpapers_route():
    if not validate_key(request):
        return jsonify({'error': 'Invalid client key'}), 401

    query = request.args.get('query')
    if query:
        client_ip = request.remote_addr
        log_query(client_ip, query)
    else:
        return jsonify({'error': 'Query parameter is required'}), 400

    image_urls = search_wallpapers(query)
    if image_urls:
        response_data = [{'Image': url} for url in image_urls]
        return jsonify(response_data), 200
    else:
        return jsonify({'error': 'No wallpapers found for the given query'}), 404

# API endpoint to view logs
@app.route('/view_logs', methods=['GET'])
def view_logs():
    if not validate_key(request):
        return jsonify({'error': 'Invalid client key'}), 401

    logs = []
    with open('ip_query_log.csv', 'r', newline='') as file:
        reader = csv.DictReader(file)
        for row in reader:
            logs.append(row)
    return jsonify(logs), 200

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
    setup_csv()  # Set up the CSV file when the server starts
    subprocess.Popen(["playit"])  # Start playit with default settings
    subprocess.run(["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--preload", "--threads", "2", "main:app"])

if __name__ == "__main__":
    run_flask_app()
