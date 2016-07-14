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

# 判断函数的参数是否是命名关键字参数，对应于*或*args传入的参数，如果是，返回True
def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

# 判断函数的参数是否是关键字参数，对应于**kw传入的参数，如果是，返回True
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

# 判断函数的参数是否有request，如果有，返回True，否则返回False
# 注意这里要求request参数要在所有参数的最后，否则会报错
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
    # 这个__call__()方法花了很长时间，依然不能很好理解，但还是尽力做一些解释：
    # 首先，可以确定的是这个__call__()的实现方式不是唯一的，廖老师的代码是实现方式之一。
    # 其次，廖老师这里首先根据request判断所调用的函数的参数类型，
    # 比如当我们请求/manage/users时，这里会判断manage_users的参数(*,page='1')的类型是否属于关键字参数，
    # 可以发现其属于命名关键字参数，那么再开始判断是post还是get类型，并分别记录body和query string，
    # 至此，还能理解，但之后的逻辑变得非常奇怪
    # 在完成对关键字参数的处理后，并不是去执行对非关键字参数的处理，而是判断此时是否获得了记录（即post的boby或get的query string），
    # 1,如果没有记录（当然对那些参数类型不是关键字参数的处理函数肯定此时就不可能获得记录了），那么开始获取request的match_info值，
    # （如果按照廖老师的这种判断，就有一个奇怪的地方，似乎是说request的query string和match_info是不共存的，即有你没我，但显然不是这样的）。
    # 2,如果有了记录，那肯定参数类型是关键字参数，但命名关键字参数才是重要的，我们删除其他关键字参数
    # （这一步搞不懂有什么必要性，所有的处理函数都不会执行这一段代码）。
    # 2,接着还是奇怪的处理：用match_info将query string的记录覆盖(似乎是match_info的优先级更高？)
    # 至此，奇怪的逻辑结束，此后部分回归正常
    # 将request参数添加到参数记录中
    # 检查是否有参数遗漏
    # 执行处理函数
    async def __call__(self, request):
        kw = None
        # 检查fn的参数
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
                    # 当post的内容为json类型时，调用json()方法，将json语句译码为一个dict
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    # post()方法返回一个MultiDictProxy实例（不懂这是个神马），一个不可变的MultiDict，一个key，对应多个values
                    # post()方法可参考http://aiohttp.readthedocs.io/en/stable/web_reference.html#aiohttp.web.Request.post
                    # MultiDict可参考http://aiohttp.readthedocs.io/en/stable/multidict.html#multidict
                    # MultiDictProxy可参考http://aiohttp.readthedocs.io/en/stable/multidict.html#multidictproxy
                    kw = dict(**params)
                    # 将MultiDictProxy转换为dict，多个values的情况只会取第一个值（不懂为什么要两个**，直接dict(params)也可以）
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                # 检查request方法是否是GET
                qs = request.query_string
                # 获取query_string查询语句，指URL中？后面的内容（为什么只取？后面）
                # 参考http://aiohttp.readthedocs.io/en/stable/web_reference.html#aiohttp.web.Request.query_string
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        # parse.parse_qs()方法，将query string转换为dict返回，第二个参数True表示保留空白字符串，即那些没有赋值的变量
                        # https://docs.python.org/3/library/urllib.parse.html?highlight=parse.parse_qs#urllib.parse.parse_qs
                        kw[k] = v[0]
                        # parse_qs()取出的value是一个单元素的list，这里需要取出真正的value值
        # 再次检查kw值，如果kw为零，表示URL中没有
        if kw is None:
            kw = dict(**request.match_info)
            # match_info获取URL中的变量keys-values对，key值直接在定义的时候确定，value值会根据key值的位置在URL中自动提取
            # 如get(/home/{name})，name是key值，实际URL请求时localhost/home/whq，whq是value值
            # match_info应该是返回一个类似dict的实例（不确定，看不懂document）
            # 可参考http://aiohttp.readthedocs.io/en/stable/web_reference.html#aiohttp.web.Request.match_info
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
            # 将request参数添加到参数记录中
            kw['request'] = request
        # 检查是否有无默认值的命名关键字参数遗漏
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            # 执行处理函数
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

# 添加一个静态路径到app中
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))

# 将某一个请求方法、路径和响应函数添加到app中，以响应request
def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))
    # add_route()方法用于将请求方法、路径和响应函数绑定并添加到app中

# 将所有响应函数添加到app中，module_name是响应函数所在的py文件名，即‘handlers’
def add_routes(app, module_name):
    # rfind() 返回字符串最后一次出现的位置，如果没有匹配项则返回-1
    n = module_name.rfind('.')
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        # 排除掉内置方法
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        # 排除掉非函数部分
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            # 筛选出拥有method和path的响应函数
            if method and path:
                # 将响应函数添加到app
                add_route(app, fn)