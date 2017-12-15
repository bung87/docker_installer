#!/usr/bin/env python

from setuptools import setup, find_packages
import os

version = '0.1.1'

setup(
    name='docker_installer',
    version=version,
    description='',
    author='bung',
    author_email='crc32@qq.com',
    license='MIT',
    keywords=['docker', 'installer', 'installation','command line', 'cli'],
    url='https://github.com/bung87/docker_installer',
    packages=['docker_installer'],
    package_dir={'docker_installer': 'docker_installer'},
    install_requires=[
        'scp',
        'BeautifulSoup'
    ],
    entry_points={
        'console_scripts': [
            'docker_installer=docker_installer.the_installer:main'
        ],
    },
    classifiers=[
        'Development Status :: 1 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)