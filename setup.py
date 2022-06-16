#!/usr/bin/env python

import setuptools

setuptools.setup(name='igniteapi',
      # packages=["igniteapi"]
      packages=setuptools.find_packages(include=['igniteapi', 'igniteapi.*']),
      version='1.0.0',
      scripts=['igniteapi/api.py'],
     )
