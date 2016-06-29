#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web

from apis import APIError

def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        # functools.wraps的功能是保证被修饰函数func的自带属性不会变化，可参考廖老师装饰器一章内容
        def wrapper(*args, **kw):
            return func(*args, **kw)
        # 添加两个属性__method__和__route__
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

def post(path):
    '''
    Define decorator @post('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

# 获得命名关键字参数的key名称，注意这里获得的key是没有指定默认值的
# 顺便一说，这个函数的实现方式真的很python，对于只有c基础的我压力好大
def get_required_kw_args(fn):
    args = []
    # inspect.signature()是一个用来对函数参数进行检查的函数，返回一个Signature实例
    # 可参考https://docs.python.org/3/library/inspect.html?highlight=inspect.signature#inspect.signature
    # 这里paramaters: An ordered mapping of parameters’ names to the corresponding Parameter objects.
    # 可参考https://docs.python.org/3/library/inspect.html?highlight=inspect.signature#inspect.Signature.parameters
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # 这里name是参数名
        # 这里param是inspect.Parameter实例，包括完整的参数信息
        # para.kind和para.default用来判断参数是否是命名关键字参数同时是否是默认值为空
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            # 如果参数为dict且没有默认值，则将参数名添加到args list中
            args.append(name)
    return tuple(args)
    # 返回一个tuple类型的args

# 获得命名关键字参数的key名，无论是否有默认值
def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

# 判断函数的参数是否是命名关键字参数，如果是，返回True
def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

# 判断函数的参数是否是关键字参数，如果是，返回True
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

# 判断函数的参数是否有request，如果有，返回True，否则返回False
# 注意这里要求request参数要在所有参数的最后，否则会报错，但依然会返回True
def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found

# RequestHandler类，用于处理各种请求
class RequestHandler(object):

    def __init__(self, app, fn):
        # 初始化，根据fn的参数初始化实例属性
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    # __call__()方法，可以将实例当作函数来调用，如rh = RequestHandler(app,fn); rh(request);
    # 这里request参数是RequestHandler作为函数时所接收的参数
    # 在aiohttp框架下，所有handler函数都只有一个参数即request，可参考http://aiohttp.readthedocs.io/en/stable/web.html#aiohttp-web-handler
    # 同时，request参数是作为一个实例传入的，可以通过调用实例属性获得http请求的全部信息，可参考http://aiohttp.readthedocs.io/en/stable/web_reference.html#request
    async def __call__(self, request):
        kw = None
        # 关键字参数，命名关键字参数和无默认值的命名关键字参数（这里重复了吧。。。），三者只要满足一个，则执行代码
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            if request.method == 'POST':
                # 检查request方法是否是POST
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower()
                # request.content_type返回string类型的content_type
                # str.lower()将str中大写全部转化成小写
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                qs = request.query_string
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        if kw is None:
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        # check required kw:
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))

def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))

def add_routes(app, module_name):
    n = module_name.rfind('.')
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)