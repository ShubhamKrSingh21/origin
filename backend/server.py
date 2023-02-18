import json
import math
import numpy as np
from flask import Flask, request
from flask_cors import CORS

import firebase_admin
from firebase_admin import credentials, firestore

from embeddings import run_kmeans

app = Flask(__name__)
CORS(app)

cred = credentials.Certificate("firebase-credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

@app.route('/')
def index():
    return json.dumps({'message': 'hello world'})

@app.route('/send-browser-history')
def send_browser_history():
    args = request.args
    username = args.get('username')
    urls = args.get('urls').split(',')
    titles = args.get('titles').split(',')
    timestamps = args.get('timestamps').split(',')

    # Push new URLs to DB
    for i in range(len(urls)):
        doc = db.collection('urls').document()
        doc.set({
            'username': username,
            'url': urls[i],
            'title': titles[i],
            'timestamp': timestamps[i]
        })

    # Fetch old URLs
    old_url_docs = db.collection('urls').where('username', '==', username).stream()
    for doc in old_url_docs:
        doc_dict = doc.to_dict()
        urls.append(doc_dict['url'])
        titles.append(doc_dict['title'])
        timestamps.append(doc_dict['timestamp'])

    kmeans = run_kmeans(titles, num_clusters=2)
    cluster_centers = kmeans.cluster_centers_

    clusters_count = db.collection('clusters').where('username', '==', username).count().get()[0][0].value
    if clusters_count == 0:
        # Create new clusters
        for i in range(cluster_centers.shape[0]):
            cluster_center = cluster_centers[i].tolist()
            doc = db.collection('clusters').document()
            doc.set({
                'username': username,
                'name': f'Unnamed Cluster {i+1}',
                'center': cluster_center
            })
    else:
        # Switch existing clusters
        clusters = db.collection('clusters').where('username', '==', username).stream()
        for cluster in clusters:
            old_center = cluster.to_dict()['center']
            old_center_np = np.array(old_center)
            best_center, best_dist = None, math.inf
            for i in range(cluster_centers.shape[0]):
                center = cluster_centers[i]
                dist = np.linalg.norm(old_center_np - center)
                if dist < best_dist:
                    best_center, best_dist = center, dist
            best_center = best_center.tolist()
            cluster.reference.update({
                'center': best_center
            })

    return json.dumps({'message': 'succeeded!'})

app.run()
