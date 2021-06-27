#!/usr/bin/env python

from setuptools import setup
import re


def find_version():
    return re.search(r"^__version__ = '(.*)'$",
                     open('bincopy.py', 'r').read(),
                     re.MULTILINE).group(1)

setup(name='bincopy',
      version=find_version(),
      description=('Mangling of various file formats that conveys '
                   'binary information (Motorola S-Record, '
                   'Intel HEX and binary files).'),
      long_description=open('README.rst', 'r').read(),
      author='Erik Moqvist',
      author_email='erik.moqvist@gmail.com',
      license='MIT',
      classifiers=[
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Programming Language :: Python :: 3.9',
      ],
      keywords=['srecord',
                'srec',
                'intel hex',
                'binary',
                '.s19',
                '.s28',
                '.s37',
                '.hex'],
      url='https://github.com/eerimoq/bincopy',
      py_modules=['bincopy'],
      install_requires=[
          'humanfriendly',
          'argparse_addons>=0.4.0',
          'pyelftools'
      ],
      python_requires='>=3.6',
      test_suite="tests",
      entry_points = {
          'console_scripts': ['bincopy=bincopy:_main']
      })
