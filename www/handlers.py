#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Hongqing Wang'

' url handlers '

from coroweb import get, post
from models import User
import logging

@get('/')
async def index(request):
    users = await User.findAll()
    logging.info('users = %s and type = %s' % (users, type(users)))
    print(dict(users=users))
    return {
        '__template__': 'test.html',
        'users': users
    }
