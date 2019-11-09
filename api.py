#!/usr/bin/python

from flask import Flask, request, jsonify, Response, stream_with_context, render_template, send_file
from base64 import b64encode, b64decode
from hashlib import md5
import json
import io

import redis
from redis_lru import redis_lru_cache
from redisearch import Client, TextField, NumericField, Query

import requests
from gzipped import gzipped
from PIL import Image, ImageOps 
import os


app = Flask(__name__)
redis_connection = redis.StrictRedis("localhost", 6379)

# For searching
client = Client('published')
PUBLISH_KEY = os.getenv('PUBLISH_KEY', "key that is def set, so dont try it")
# This index already exists, and must be made
#client.drop_index()
#client.create_index([TextField('title', weight=5.0), TextField('description', weight=2.0), NumericField('favs'), NumericField('highscore'), TextField('match')])


def hash(url):
  hashed = b64encode(md5(url.encode(encoding='UTF-8',errors='strict')).digest())
  return hashed[:16].replace('/', '_')


def serve_pil_image(pil_img):
  img_io = io.BytesIO()
  pil_img.save(img_io, 'PNG')
  img_io.seek(0)
  return send_file(img_io, mimetype='image/png')


@app.route('/', methods=['POST'])
def create_short_url():
  # TODO: Add CSRF tokens
  data = request.form['data']
  lookup = hash(data)
  redis_connection.set(lookup, data, nx=True)
  return jsonify({'lookup':lookup})


@app.route('/<string:lookup>')
def get_long_url(lookup):
  data = redis_connection.get(lookup)
  return jsonify({'valid': data is not None, 'data': data})


@app.route('/app/<string:lookup>/')
def get_app(lookup):
  return render_template('frame.html')


@app.route('/app/<string:lookup>/manifest.json')
def get_manifest(lookup):
  data = redis_connection.get(lookup)
  data = json.loads(b64decode(data))
  name = data.get("meta",{}).get("name", "GameFrame")
  response = render_template('manifest.json', lookup=lookup, name=name)
  return Response(response, mimetype='application/javascript')


@app.route('/app/<string:lookup>/<int:size>.png')
def get_icon(lookup, size):
  data = redis_connection.get(lookup)
  data = json.loads(b64decode(data))
  src = data.get("meta",{}).get("icon", "https://editor.carolinaignites.org/launcher-icon-4x.png")

  img, content_type = get_image(src)
  img = Image.open(io.BytesIO(img))
  img = ImageOps.fit(img, (size, size,), method=Image.ANTIALIAS)
  return serve_pil_image(img) 


@app.route('/app/<string:lookup>/sw.js')
def get_sw(lookup):
  data = redis_connection.get(lookup)
  data = json.loads(b64decode(data))
  name = data.get("meta",{}).get("name", "GameFrame")
  response = render_template('sw.js', lookup=lookup, name=name)
  return Response(response, mimetype='application/javascript')


@redis_lru_cache(max_size=256, node=redis_connection)
def get_image(url):
  req = requests.get(url)
  return req.content, req.headers.get('content-type') 


@app.route('/cors/<path:url>')
@gzipped
def proxy(url):
  data, content_type = get_image(url + "?" + request.query_string)
  response = Response(data, content_type=content_type)
  del response.headers['Access-Control-Allow-Origin']
  response.headers['x-requested-with'] = 'ignite-api'
  return response


@app.route('/publish/<string:publish_key>/<string:lookup>')
def publish(publish_key, lookup):
  if publish_key != PUBLISH_KEY:
    return "Boo. Don't hack us"
  data = redis_connection.get(lookup)
  if data is None:
    return "Bad lookup hash"

  data = json.loads(b64decode(data))
  src = data.get("meta",{}).get("icon", "https://editor.carolinaignites.org/launcher-icon-4x.png")
  title = data.get("meta",{}).get("name", "No title")
  description = data.get("meta",{}).get("instructions", "No description")
  lookup = "published_" + lookup.strip()
  client.add_document(lookup, payload=src, title=title, body=description, favs=0, highscore=0, match="*")
  return "Success!"


@app.route('/unpublish/<string:publish_key>/<string:lookup>')
def unpublish(publish_key, lookup):
  if publish_key != PUBLISH_KEY:
    return "Boo. Don't hack us"
  return ["Didn't work", "Worked"][client.delete_document("published_" +lookup)]


@app.route('/search')
def search():
  query = request.args.get("search")
  res = client.search(Query(query).limit_fields('title', 'body').with_payloads())
  return jsonify({
    "results": [doc.__dict__ for doc in res.docs],
    "total": res.total
  })


@app.route('/some')
def some():
  res = client.search(Query("*").limit_fields('match').paging(0, 5).with_payloads())
  return jsonify({
    "results": [doc.__dict__ for doc in res.docs],
    "total": res.total
  })


app.run()
