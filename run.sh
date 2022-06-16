#!/usr/bin/env bash
fuser -k 5000/tcp
gunicorn --bind :5000 api --daemon
