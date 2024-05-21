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
from cachetools import TTLCache
from collections import Counter

app = Flask(__name__)
CORS(app)
px = PeakPx()

# Server key
server_key = "wallartify2024new"

# Setup CSV file for logging queries
def setup_csv():
    csv_file = 'ip_query_log.csv'
    if not os.path.exists(csv_file):
        try:
            with open(csv_file, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["ID", "IP Address", "Query", "Timestamp", "Response Status"])
        except Exception as e:
            print(f"Error setting up CSV file: {e}")

# Dictionary to store client IPs and their corresponding IDs
client_ids = {}

# Log query to CSV
def log_query(ip_address, query, response_success, file):
    try:
        if ip_address not in client_ids:
            client_ids[ip_address] = str(uuid.uuid4())
        unique_id = client_ids[ip_address]
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

# Caching results of the search for 5 minutes
cache = TTLCache(maxsize=100, ttl=300)

# Search wallpapers using PeakPx API
def search_wallpapers(query):
    if query in cache:
        return cache[query], True

    try:
        wallpapers = px.search_wallpapers(query=query)
        if wallpapers:
            image_urls = [wallpaper['url'] for wallpaper in wallpapers]
            cache[query] = image_urls
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
def partial_query_recommendation(partial_query, queries, query_counter, vectorizer, model, top_n=5):
    try:
        partial_vec = vectorizer.transform([partial_query.lower()])
        similarities = cosine_similarity(partial_vec, vectorizer.transform(queries)).flatten()
        sorted_indices = np.argsort(similarities)[::-1]

        unique_recommendations = []
        seen = set()
        for idx in sorted_indices:
            if queries[idx].startswith(partial_query.lower()) and queries[idx] not in seen:
                unique_recommendations.append((queries[idx], query_counter[queries[idx]]))
                seen.add(queries[idx])
            if len(unique_recommendations) == top_n:
                break

        # Sort by frequency
        unique_recommendations.sort(key=lambda x: (-x[1], x[0]))

        return [recommendation for recommendation, _ in unique_recommendations]
    except Exception as e:
        print(f"Error in partial_query_recommendation: {e}")
        return []

# Load data from CSV file for logging queries
def load_data(filename):
    queries = []
    try:
        with open(filename, 'r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                queries.append(row['Query'].lower())
    except Exception as e:
        print(f"Error loading data: {e}")
    return queries

# API endpoint to search wallpapers
@app.route('/search_wallpapers', methods=['GET'])
def search_wallpapers_route():
    if not validate_key(request):
        return jsonify({'error': 'Invalid client key'}), 401

    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400

    client_ip = request.remote_addr
    image_urls, success = search_wallpapers(query)
    with open('ip_query_log.csv', 'a', newline='') as file:
        log_query(client_ip, query, success, file)

    if success:
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
    try:
        with open('ip_query_log.csv', 'r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                logs.append({'ID': row['ID'], 'IP Address': row['IP Address'], 'Query': row['Query'], 'Timestamp': row['Timestamp'], 'Response Success': row['Response Status']})
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred'}), 500

    return jsonify(logs), 200

# API endpoint to get recommendations for partial queries
@app.route('/recommendations', methods=['GET'])
def get_recommendations():
    if not validate_key(request):
        return jsonify({'error': 'Invalid client key'}), 401

    partial_query = request.args.get('q')
    if not partial_query:
        return jsonify({'error': 'Partial query parameter (q) is required'}), 400

    queries = load_data('ip_query_log.csv')
    query_counter = Counter(queries)
    vectorizer, model = train_model(queries)
    recommendations = partial_query_recommendation(partial_query, queries, query_counter, vectorizer, model)
    recommendations_list = [{'recommend': recommendation} for recommendation in recommendations]

    return jsonify(recommendations_list), 200

# API endpoint to get trending queries
@app.route('/trending', methods=['GET'])
def get_trending():
    if not validate_key(request):
        return jsonify({'error': 'Invalid client key'}), 401

    queries = load_data('ip_query_log.csv')
    trending_queries = Counter(queries).most_common(10)
    trending_list = [{'query': query, 'count': count} for query, count in trending_queries]

    return jsonify(trending_list), 200

def run_flask_app():
    setup_csv()

    try:
        print("Starting server...")
        time.sleep(1)
        print("Server started successfully!")

        playit_proc = subprocess.Popen(["playit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        print("Playit started successfully!")

        subprocess.run(["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", "main:app"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Error running Flask app: {e}")

def signal_handler(sig, frame):
    print("Exiting...")
    exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    run_flask_app()
        
