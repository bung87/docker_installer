#!/usr/bin/env python

from setuptools import setup, find_packages
import os,sys
import pkg_resources

version = '0.1.1'

install_requires = [
    'scp'
]

extras_require = {
    ":python_version>='3'": ['beautifulsoup4'],
    ":python_version<'3'": ['BeautifulSoup']
}

try:
    if 'bdist_wheel' not in sys.argv:
        for key, value in extras_require.items():
            if key.startswith(':') and pkg_resources.evaluate_marker(key[1:]):
                install_requires.extend(value)
except Exception as e:
    print("Failed to compute platform dependencies: {}. ".format(e) +   "All dependencies will be installed as a result.")
    for key, value in extras_require.items():
        if key.startswith(':'):
            install_requires.extend(value)
    extras_require = {}

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
    extras_require=extras_require,
    install_requires=install_requires,
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