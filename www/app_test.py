# 导入需要用到的模块
import logging
logging.basicConfig(level=logging.INFO)
# logging将日志打印到屏幕，默认级别为warning
# 日志级别大小关系为：critical>error>warning>info>debug>notset
# 可以在basicConfig中自定义日志级别

import asyncio, os, json, time
from datetime import datetime
from aiohttp import web

# a request handler is a coroutine or regular function that accepts
#   a Request instance as its only parameter and returns a Response instance
# 详见http://aiohttp.readthedocs.io/en/stable/web.html
def index(request):
    return web.Response(body=b'<h1>Awesome</h1>')
    # aiohttp.web.Response类
    # 接受变量body(bytes)用于HTTP页面响应，将body的内容作为HTTP页面BODY部分
    # 详见http://aiohttp.readthedocs.io/en/stable/web_reference.html#aiohttp.web.Response

# create an Application instance and register the request handler with
#   the application's router on a particular HTTP method and path:
# 详见http://aiohttp.readthedocs.io/en/stable/web.html
async def init(loop):
    app = web.Application(loop=loop)
    # aiohttp.web.Application类
    # 创建一个Application实例，用来响应客户端到某种操作，如GET‘/’目录
    # 详见http://aiohttp.readthedocs.io/en/stable/web_reference.html#aiohttp.web.Application
    app.router.add_route('GET', '/', index)
    # add_route(method,path,handler,*,name=None,expect_handler=None)方法
    # 详见http://aiohttp.readthedocs.io/en/stable/web_reference.html#aiohttp.web.UrlDispatcher.add_route
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    # creater_server创建一个绑定了host和port的TCP server，返回一个Server对象
    # 详见https://docs.python.org/3/library/asyncio-eventloop.html?highlight=create_server#asyncio.BaseEventLoop.create_server
    # make_handler()用于创建一个HTTP protocol factory来处理请求
    # 详见http://aiohttp.readthedocs.io/en/stable/web_reference.html#aiohttp.web.Application.make_handler
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()

