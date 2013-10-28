#!/usr/bin/env python
#encoding: utf-8
"""
Fabric decorets mess up all the autoloading of the functions, so to generate
the doc we must read the source files...
"""

import os
import sys
from subprocess import call


PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PATH)


def main():
    ## generate the html files
    os.environ['PYTHONPATH'] = ':'.join(sys.path)
    call(['make', 'html'])


if __name__ == '__main__':
    main()
