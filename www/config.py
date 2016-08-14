#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
Configuration
'''

__author__ = 'Hongqing Wang'

import config_default

# 定义一个Dict类，添加了__getattr__()和__setattr__()方法
# 这里names和values可以以tuple的形式作为参数（为什么不直接就以dict形式，因为方便？）
class Dict(dict):
    '''
    Simple dict but support access as x.y style.
    '''
    def __init__(self, names=(), values=(), **kw):
        super(Dict, self).__init__(**kw)
        for k, v in zip(names, values):
            self[k] = v

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

# 将default文件和override文件进行合并,重复部分用override进行覆盖
# 由于default文件中可能是dict中套dict，所以这是一个递归函数，对dict的值进行多次检测，直到值不是dict为止
def merge(defaults, override):
    r = {}
    # 遍历configs这个dict的key-value值
    for k, v in defaults.items():
        # 检查key值是否也在override的configs中出现
        if k in override:
            # 检查value值是否是dict，如果是，则递归merge函数再次对value值进行遍历
            # 直到value值不是dict，则将override中对应的value值覆盖default的
            if isinstance(v, dict):
                r[k] = merge(v, override[k])
            else:
                r[k] = override[k]
        # 如果key值没有在override中出现，则仍然使用default中value值
        else:
            r[k] = v
    return r

# 将dict套dict的形式展开成一个dict，这样在程序中运行会方便很多
def toDict(d):
    D = Dict()
    for k, v in d.items():
        D[k] = toDict(v) if isinstance(v, dict) else v
    return D

configs = config_default.configs

try:
    import config_override
    configs = merge(configs, config_override.configs)
except ImportError:
    pass

# 将configs的dict套dict展开，这样在程序中运行会方便很多
configs = toDict(configs)