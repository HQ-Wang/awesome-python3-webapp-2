#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Hongqing Wang'

' url handlers '

from coroweb import get, post

@get('/')
def index(*, page='1', a:int):
    pass
