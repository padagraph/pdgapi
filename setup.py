#!/usr/bin/env python

from setuptools import setup, find_packages

#TODO; better setup
# see https://bitbucket.org/mchaput/whoosh/src/999cd5fb0d110ca955fab8377d358e98ba426527/setup.py?at=default
# for ex

# Read requirements from txt file
required = []
with open('requirements.txt') as f:
    required = [ e for e in f.read().splitlines() if e[0]!= "#" ]


required = []

setup(
    name='pdgapi',
    version='1.0.3',
    description='padagraph api endpoints',
    author='ynnk, a-tsioh',
    author_email='contact@padagraph.io',
    url='www.padagraph.io',
    packages=['pdgapi'] + ['pdgapi.%s' % submod for submod in find_packages('pdgapi')],
    install_requires=required
)
