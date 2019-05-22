#!/usr/bin/python

from flask import Flask, request, jsonify, Response, stream_with_context, render_template, send_file
from base64 import b64encode, b64decode
from hashlib import md5
import json
import io
import redis
from redis_lru import redis_lru_cache
import requests
from gzipped import gzipped
from PIL import Image, ImageOps


app = Flask(__name__)
redis_connection = redis.StrictRedis("localhost", 6379)


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

app.run()
