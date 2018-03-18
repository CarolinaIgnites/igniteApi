from flask import Flask, abort, make_response, redirect, request, url_for, render_template
import base64, hashlib

import redis

app = Flask(__name__)
redis_connection = redis.StrictRedis("localhost", 6379)

def minihash(url):
    return base64.b64encode(hashlib.md5(url.encode(encoding='UTF-8',errors='strict')).digest())[:6]


@app.route('/')
def index():
	return render_template('index.html', iframe = 'frame.html')

@app.route('/frame.html')
def frame():
	return render_template('frame.html')


@app.route('/create', methods=['POST'])
def create_short_url():
	long_hash = request.form['hash']
	short_hash = minihash(long_hash)
	short_hash.replace('/', '_')
	redis_connection.set(short_hash, long_hash, nx=True)
	print(short_hash)
	#return short_hash
	return render_template("index.html", short_hash = short_hash)


@app.route('/<string:short>')
def get_long_url(short):
	long_hash = redis_connection.get(short)

	if (long_hash != None):
		long_url = '/#' + long_hash
		return redirect(long_url)
	else:
	 #if the short code doesn't exist go home
		return redirect('/')


if __name__ == "__main__":
    app.debug = True
    app.run()