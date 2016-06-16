#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Hongqing Wang'

import asyncio, logging

import aiomysql

# 编写log函数：用于打印sql语句
def log(sql, args=()):
    logging.info('SQL: %s' % sql)

# 编写create_pool() coroutine：用于创建连接池中到各种参数
async def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    global __pool
    __pool = await aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )
    # aiomysqld的create_pool()方法，a coroutine that creates a pool of connections to MySQL database，返回一个pool实例
    # 详见http://aiomysql.readthedocs.io/en/latest/pool.html?highlight=create_pool#create_pool

# 编写select() coroutine：用于提取出指定数据库中的指定行数据或者全部行数据
async def select(sql, args, size=None):
    log(sql, args)
    global __pool
    async with __pool.get() as conn:
        # 没有找到pool.get()方法，怀疑是acquire（）方法，本身即为一个coroutine，用于创建返回一个Connection实例
        # 详见http://aiomysql.readthedocs.io/en/latest/pool.html#Pool
        # async with是python3.5新加入到语法，可参考http://my.oschina.net/cppblog/blog/469926
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # 创建一个dict类型的cursor，可参考http://aiomysql.readthedocs.io/en/latest/cursors.html?highlight=dic#DictCursor
            await cur.execute(sql.replace('?', '%s'), args or ())
            # execute(query,args=None)方法用于执行sql语句，sql语句中到占位符是？，MySQL的占位符是%s，sql.replace()用于将？替换为%s
            # 详见http://aiomysql.readthedocs.io/en/latest/cursors.html?highlight=dic#Cursor.execute
            if size:
                # 如果要求获取the next set of rows of a query result，执行fetchmany()方法
                rs = await cur.fetchmany(size)
                # fetchmany(size=None)方法，返回一个tuple类型的list
                # 详见http://aiomysql.readthedocs.io/en/latest/cursors.html?highlight=fetchmany#Cursor.fetchmany
            else:
                # 否则获取全部行信息，
                rs = await cur.fetchall()
                # 详见http://aiomysql.readthedocs.io/en/latest/cursors.html?highlight=fetchmany#Cursor.fetchall
        logging.info('rows returned: %s' % len(rs))
        return rs

# 编写execute() coroutine：用于执行insert，update，delete语句（以sql语句写入），返回一个整数表示影响的行数
async def execute(sql, args, autocommit=True):
    log(sql)
    async with __pool.get() as conn:
        if not autocommit:
            # 如果不是自动提交，则采用手动提交，手动提交采用conn.begin()与conn.commit()/conn.rollback()配合使用
            # 详见http://aiomysql.readthedocs.io/en/latest/sa.html?highlight=conn.begin#aiomysql.sa.SAConnection.begin
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                affected = cur.rowcount
                # cur.rowcount用于获得影响的行数
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            # 抛出BaseException错误，可参考廖雪峰老师“错误处理”章节
            if not autocommit:
                await conn.rollback()
            raise e
        return affected

# 生成一个由num个"?"组成的字符串，如"?, ?, ?, ?"
def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ', '.join(L)

# 定义Field类
class Field(object):

    def __init__(self, name, column_type, primary_key, default):
        # __init__()方法，初始化name, column_type, primary_key, default属性
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        # __str__()方法，返回<类名, 列类型：名字>
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

class StringField(Field):

    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)

class BooleanField(Field):

    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)

class IntegerField(Field):

    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)

class FloatField(Field):

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)

class TextField(Field):

    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)

class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        if name=='Model':
            return type.__new__(cls, name, bases, attrs)
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        mappings = dict()
        fields = []
        primaryKey = None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('  found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                if v.primary_key:
                    # 找到主键:
                    if primaryKey:
                        raise StandardError('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)
        if not primaryKey:
            raise StandardError('Primary key not found.')
        for k in mappings.keys():
            attrs.pop(k)
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__mappings__'] = mappings # 保存属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey # 主键属性名
        attrs['__fields__'] = fields # 除主键外的属性名
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)