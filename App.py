import subprocess
import time
import csv
import os
import signal
import sched  # Import the 'sched' module for scheduling tasks
from flask import Flask, request, jsonify
from flask_cors import CORS
from PeakPxApi import PeakPx
from gunicorn.app.base import BaseApplication
import uuid

app = Flask(__name__)
CORS(app)
px = PeakPx()
scheduler = sched.scheduler(time.time, time.sleep)  # Define the scheduler

# Server key
server_key = "wallartify2024new"

# Setup CSV file for logging queries
def setup_csv():
    try:
        if not os.path.exists('ip_query_log.csv'):
            with open('ip_query_log.csv', 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["ID", "IP Address", "Query", "Timestamp", "Response Status"])
    except Exception as e:
        print(f"Error setting up CSV file: {e}")

# Dictionary to store client IPs and their corresponding IDs
client_ids = {}

# Log query to CSV
def log_query(ip_address, query, response_success):
    try:
        if ip_address not in client_ids:
            client_ids[ip_address] = str(uuid.uuid4())
        unique_id = client_ids[ip_address]
        with open('ip_query_log.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            writer.writerow([unique_id, ip_address, query, timestamp, response_success])
    except Exception as e:
        print(f"Error logging query: {e}")

# Validate client key
def validate_key(request):
    try:
        client_sent_key = request.args.get('key')
        return client_sent_key == server_key
    except Exception as e:
        print(f"Error validating client key: {e}")
        return False

# Search wallpapers using PeakPx API
def search_wallpapers(query):
    try:
        wallpapers = px.search_wallpapers(query=query)
        if wallpapers:
            image_urls = [wallpaper['url'] for wallpaper in wallpapers]
            return image_urls, True
        else:
            return [], False
    except Exception as e:
        print(f"Error searching wallpapers: {e}")
        return [], False

# API endpoint to search wallpapers
@app.route('/search_wallpapers', methods=['GET'])
def search_wallpapers_route():
    try:
        if not validate_key(request):
            print("Invalid client key")
            return jsonify({'error': 'Invalid client key'}), 401

        query = request.args.get('query')
        if query:
            client_ip = request.remote_addr  # Get IP from request
            print(f"Request from IP: {client_ip}, Query: {query}")
            image_urls, success = search_wallpapers(query)
            log_query(client_ip, query, success)
            if success:
                response_data = [{'Image': url} for url in image_urls]
                return jsonify(response_data), 200
            else:
                return jsonify({'error': 'No wallpapers found for the given query'}), 404
        else:
            print("Query parameter is required")
            return jsonify({'error': 'Query parameter is required'}), 400
    except Exception as e:
        print(f"Error in search_wallpapers_route: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

# API endpoint to view logs
@app.route('/view_logs', methods=['GET'])
def view_logs():
    try:
        if not validate_key(request):
            print("Invalid client key")
            return jsonify({'error': 'Invalid client key'}), 401

        logs = []
        with open('ip_query_log.csv', 'r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                logs.append({'ID': row['ID'], 'IP Address': row['IP Address'], 'Query': row['Query'], 'Timestamp': row['Timestamp'], 'Response Success': row['Response Success']})
        return jsonify(logs), 200
    except Exception as e:
        print(f"Error in view_logs: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

class StandaloneApplication(BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        try:
            config = {key: value for key, value in self.options.items() if key in self.cfg.settings and value is not None}
            for key, value in config.items():
                self.cfg.set(key.lower(), value)
        except Exception as e:
            print(f"Error loading config: {e}")

    def load(self):
        return self.application

def run_flask_app():
    try:
        setup_csv()  # Set up the CSV file when the server starts
        print("Starting server...")
        time.sleep(1)
        print("Server started successfully!")
        
        subprocess.Popen(["playit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # Start playit with default settings
        time.sleep(2)
        print("Playit started successfully!")
        
        subprocess.run(["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--preload", "--threads", "2", "main:app"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # Hide Gunicorn logs
    except Exception as e:
        print(f"Error running Flask app: {e}")

def restart_script(sc):
    print("Restarting script...")
    subprocess.Popen(["python", "main.py"])  # Restart the script
    print("Script restarted successfully!")
    # Reschedule the restart
    scheduler.enter(7200, 1, restart_script, (sc,))

def signal_handler(sig, frame):
    print("Exiting...")
    exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)  # Register signal handler for Ctrl+C
    scheduler.enter(7200, 1, restart_script, (scheduler,))
    run_flask_app()
    scheduler.run()
