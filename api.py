#!/usr/bin/python

from flask import Flask, request, jsonify, render_template
from base64 import b64encode
from hashlib import md5
import redis
import requests


app = Flask(__name__, template_folder="templates")
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

@app.route('/khalid/<path:imgurl>')
def get_khalid(imgurl):
    headers = {'Access-Control-Allow-Origin' : '*'}
    r = requests.get(imgurl, headers = headers)
    return render_template('test.html', user_image = r.url)


app.run()
