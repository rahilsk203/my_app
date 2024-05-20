import subprocess
import time
import csv
import os
import signal
from flask import Flask, request, jsonify
from flask_cors import CORS
from PeakPxApi import PeakPx
import uuid
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
CORS(app)
px = PeakPx()

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
            writer.writerow([unique_id, ip_address, query.lower(), timestamp, response_success])
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

# Train model for recommendation system
def train_model(queries):
    vectorizer = TfidfVectorizer(stop_words='english')
    X = vectorizer.fit_transform(queries)
    kmeans = KMeans(n_clusters=5, random_state=0)
    kmeans.fit(X)
    return vectorizer, kmeans

# Partial query recommendation function
def partial_query_recommendation(partial_query, queries, vectorizer, model, top_n=5):
    try:
        partial_vec = vectorizer.transform([partial_query.lower()])
        similarities = cosine_similarity(partial_vec, vectorizer.transform(queries)).flatten()
        sorted_indices = np.argsort(similarities)[::-1]

        unique_recommendations = []
        seen = set()
        for idx in sorted_indices:
            # Check if the query starts with the input prefix
            if queries[idx].startswith(partial_query.lower()) and queries[idx] not in seen:
                unique_recommendations.append(queries[idx])
                seen.add(queries[idx])
            if len(unique_recommendations) == top_n:
                break

        return unique_recommendations
    except Exception as e:
        print(f"Error in partial_query_recommendation: {e}")
        return []

# Load data from CSV file for logging queries
def load_data(filename):
    queries = []
    with open(filename, 'r', newline='') as file:
        reader = csv.DictReader(file)
        for row in reader:
            queries.append(row['Query'].lower())
    return queries

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
                logs.append({'ID': row['ID'], 'IP Address': row['IP Address'], 'Query': row['Query'], 'Timestamp': row['Timestamp'], 'Response Success': row['Response Status']})
        return jsonify(logs), 200
    except Exception as e:
        print(f"Error in view_logs: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

# API endpoint to get recommendations for partial queries
@app.route('/recommendations', methods=['GET'])
def get_recommendations():
    try:
        if not validate_key(request):
            print("Invalid client key")
            return jsonify({'error': 'Invalid client key'}), 401

        partial_query = request.args.get('q')
        if partial_query:
            queries = load_data('ip_query_log.csv')
            vectorizer, model = train_model(queries)
            recommendations = partial_query_recommendation(partial_query, queries, vectorizer, model)
            recommendations_list = [{'recommend': recommendation} for recommendation in recommendations]
            return jsonify(recommendations_list), 200
        else:
            return jsonify({'error': 'Partial query parameter (q) is required'}), 400
    except Exception as e:
        print(f"Error in get_recommendations: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

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

def signal_handler(sig, frame):
    print("Exiting...")
    exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)  # Register signal handler for Ctrl+C
    run_flask_app()
