#!/usr/bin/python3

from flask import Flask, request, jsonify, Response, stream_with_context, render_template, send_file
from base64 import b64encode, b64decode
from hashlib import md5
import json
import io
import string
import random

import redis
from redis_lru import RedisLRU
from redisearch import Client, TextField, NumericField, Query

import requests
from gzipped import gzipped
from PIL import Image, ImageOps 
import os

from flask_cors import CORS, cross_origin

app = Flask(__name__)
# CORS(app)

redis_connection = redis.StrictRedis("localhost", 6379)

cache = RedisLRU(redis_connection, max_size=512)

# For searching
client = Client('published')
PUBLISH_KEY = os.getenv('PUBLISH_KEY', "key that is def set, so dont try it")
# This index already exists, and must be made
#client.drop_index()
#client.create_index([TextField('title', weight=5.0), TextField('description', weight=2.0), NumericField('favs'), NumericField('highscore'), TextField('match')])


def hasher(url, lookup, recursed=False):
  seed = b64encode(md5(url.encode(encoding='UTF-8', errors='strict')).digest())
  random.seed(seed[:32])
  # Gives us a cleaner string than a b64 (also more random)
  hashed = ''.join(random.choice(string.ascii_lowercase +
      string.ascii_uppercase + string.digits) for _ in range(16))

  # Do not update if nothing has changed.
  if not recursed and len(lookup) > 16 and redis_connection.get(lookup) is not None:
    splits = lookup.split("-")
    if redis_connection.get("prev_" + lookup).decode("utf-8") != hashed:
        # Increment the inital hash by 1. In theory increment is atomic and
        # this should be race-condition safe.
        lookup = splits[0] + "-" + str(redis_connection.incr("count_" + splits[0]))
        redis_connection.set("prev_" + lookup, hashed)
    return lookup

  # Change to see if somehow we have a hash collision. This is laughably
  # unlikely normally, but we offer the option to generate a new link. A new
  # link means a new context and should have a new hash.
  data = redis_connection.get("count_" + hashed)
  if data is not None:
    return hasher(url + hashed, lookup, True)
  redis_connection.incr("count_" + hashed)
  lookup = hashed + "-0"
  redis_connection.set("prev_" + lookup, hashed)
  return lookup


def serve_pil_image(pil_img):
  img_io = io.BytesIO()
  pil_img.save(img_io, 'PNG')
  img_io.seek(0)
  return send_file(img_io, mimetype='image/png')


def change_fav(lookup, delta):
  doc = client.load_document(lookup)
  doc.favs += delta
  doc.favs = min(doc.favs, 0)
  client.add_document(lookup, partial=True, favs=doc.favs)
  return 202


@app.route('/', methods=['POST'])
def create_short_url():
  # TODO: Add CSRF tokens
  data = request.form['data']
  lookup = hasher(data, request.form['hash'][1:])
  redis_connection.set(lookup, data, nx=True)
  return jsonify({'lookup':lookup})


@app.route('/<string:lookup>')
def get_long_url(lookup):
  data = redis_connection.get(lookup)
  if data is not None:
    return jsonify({'valid': True, 'data': data.decode("utf-8")})
  return jsonify({'valid': False, 'data': None})


@app.route('/app/<string:lookup>/')
def get_app(lookup):
  return render_template('frame.html')


@app.route('/app/<string:lookup>/manifest.json')
def get_manifest(lookup):
  data = redis_connection.get(lookup)
  data = json.loads(b64decode(data).decode("utf-8"))
  name = data.get("meta",{}).get("name", "GameFrame")
  response = render_template('manifest.json', lookup=lookup, name=name)
  return Response(response, mimetype='application/javascript')


@app.route('/app/<string:lookup>/<int:size>.png')
def get_icon(lookup, size):
  data = redis_connection.get(lookup)
  data = json.loads(b64decode(data).decode("utf-8"))
  src = data.get("meta",{}).get("icon", "https://editor.carolinaignites.org/launcher-icon-4x.png")
  img, content_type = get_image(src)
  img = Image.open(io.BytesIO(img))
  img = ImageOps.fit(img, (size, size,), method=Image.ANTIALIAS)
  return serve_pil_image(img) 


@app.route('/app/<string:lookup>/sw.js')
def get_sw(lookup):
  data = redis_connection.get(lookup)
  data = json.loads(b64decode(data).decode("utf-8"))
  name = data.get("meta",{}).get("name", "GameFrame")
  response = render_template('sw.js', lookup=lookup, name=name)
  return Response(response, mimetype='application/javascript')


@cache
def get_image(url):
  req = requests.get(url)
  return req.content, req.headers.get('content-type') 


@app.route('/cors/<path:url>')
@gzipped
def proxy(url):
  data, content_type = get_image(url + "?" + request.query_string.decode("utf-8"))
  response = Response(data, content_type=content_type)
  del response.headers['Access-Control-Allow-Origin']
  response.headers['x-requested-with'] = 'ignite-api'
  response.cache_control.max_age = 31536000
  return response


@app.route('/publish/<string:publish_key>/<string:lookup>')
def publish(publish_key, lookup):
  if publish_key != PUBLISH_KEY:
    return "Boo. Don't hack us"
  data = redis_connection.get(lookup)
  if data is None:
    return "Bad lookup hash"

  data = json.loads(b64decode(data).decode('utf-8'))
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


@app.route('/unfav/<string:lookup>')
def unfav(lookup):
  return change_fav(lookup, -1)

@app.route('/fav/<string:lookup>')
def fav(lookup):
  return change_fav(lookup, 1)

@app.route('/highscore/<string:lookup>/<int:score>')
def highscore(lookup, score):
  client.load_document(lookup)
  if score > lookup.highscore:
    client.add_document(lookup, partial=True, favs=score)
    return 202
  return 406


@app.route('/search')
def search():
  query = request.args.get("search") + "*"
  res = client.search(Query(query).limit_fields('title', 'body').with_payloads())
  return jsonify({
    "results": [doc.__dict__ for doc in res.docs],
    "total": res.total
  })


@app.route('/some/<int:page>')
def some(page):
  res = client.search(Query("*").limit_fields('match').paging(page, 5).with_payloads())
  return jsonify({
    "results": [doc.__dict__ for doc in res.docs],
    "total": res.total
  })

@app.route('/some')
def some0():
    return some(0)

app.run()
