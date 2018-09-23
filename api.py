#!/usr/bin/python

from flask import Flask, request, jsonify
from base64 import b64encode
from hashlib import md5
import redis
import requests

from flask import Response
from flask import stream_with_context


app = Flask(__name__)
redis_connection = redis.StrictRedis("localhost", 6379)


def hash(url):
  hashed = b64encode(md5(url.encode(encoding='UTF-8',errors='strict')).digest())
  return hashed[:16].replace('/', '_')


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

@app.route('/cors/<path:url>')
def proxy(url):
    headers = {'Access-Control-Allow-Origin' : '*'}
    resp = requests.get(url, headers = headers)
    print(resp.headers)
    return Response(stream_with_context(resp.iter_content()), content_type = resp.headers['content-type'])


app.run()
