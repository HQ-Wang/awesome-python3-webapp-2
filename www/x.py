import aiohttp

d = aiohttp.MultiDict([('a', 1), ('b', 2), ('a', 3)])

print(dict(d))