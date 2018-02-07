#!/usr/bin/env python3
import os

from setuptools import setup, find_packages

def list_of_files_in_directory(path):
    return [
        os.path.join(path, x) for x in os.listdir(path)
    ]

scripts = list_of_files_in_directory('bin')

setup(
    name='Janrain PS Deployment Tools',
    version='0.1dev',
    long_description=open('README.md').read(),
    author="Janrain",
    author_email="pse@janrain.com",
    url="https://github.com/Janrain/ps-deploy.git",
    license='Creative Commons Attribution-Noncommercial-Share Alike license',

    # what to include in the package
    packages=find_packages(),
    scripts=scripts,
    # dependencies (to be automatically installed or updated)
    install_requires=[
        'boto3'
    ]
)
