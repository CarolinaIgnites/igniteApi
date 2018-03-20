#!/bin/bash

gunicorn --bind :8080 api --daemon
