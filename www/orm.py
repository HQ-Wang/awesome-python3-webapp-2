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

async def execute(sql, args, autocommit=True):
    log(sql)
    async with __pool.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                affected = cur.rowcount
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            if not autocommit:
                await conn.rollback()
            raise
        return affected