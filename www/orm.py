#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Hongqing Wang'

import asyncio, logging

import aiomysql

import logging
logging.basicConfig(level=logging.INFO)
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
                # 官方注解有误，这里rs返回的是一个list，其中的元素都是dict，类似[{'id':1, 'passwd':123},{'id':2, 'passwd':456}]这样
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

    # __new__()方法优先级高于__init__(),用于对类名，基类，类属性进行修改
    # 作用是把类和数据库表做一个映射，如经过__new__()方法将User类重建
    # 这样做的好处是把类属性创建和创建数据库映射相互分开，利于维护
    # 最后修改完成的类具有1个反映映射关系的__mappings__属性，1个表名属性，2个键值属性和4个sql语句属性共8个属性
    def __new__(cls, name, bases, attrs):
        # cls类似于self
        # name为类名，如'User'
        # bases为list型基类合集，这里似乎没什么用
        # attrs为dict型类属性合集，如User类中的类属性key-value合集
        if name=='Model':
            # 这里排除对Model类的修改，如果发现是Model类，直接结束__new__()方法
            # 因为Model类是用来定义各种方法的，不涉及类属性创建，不需要修改
            return type.__new__(cls, name, bases, attrs)
        tableName = attrs.get('__table__', None) or name
        # 数据库表名，若User类中定义了'__table__'则作为表名，否则就以类名User作为表名
        logging.info('found model: %s (table: %s)' % (name, tableName))
        mappings = dict()
        fields = []
        primaryKey = None
        # 将类属性打包到mappings这个dict中
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('  found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                if v.primary_key:
                    # 找到主键，主键只有一个，所有Field子类都默认没有主键,但都可以设为主键，这里统一将id设为主键
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
        # 这里map外面要套一个list才能获得值，是python3的一个变化，至于原因现在太菜没太搞明白，似乎是为了提高运算效率
        # 反引号``似乎是sql语句的语法要求
        attrs['__mappings__'] = mappings # 保存属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey # 主键属性名
        attrs['__fields__'] = fields # 除主键外的属性名
        # 以下四句均为sql语句，'?'表示占位符，用于动态赋值
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % f, fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)

# Model类这里作为基类使用，负责定义各种方法将继承到子类
class Model(dict, metaclass=ModelMetaclass):

    # __init__()方法，**kw为关键字参数，可以传入任意多的dict参数。配合__getattr__()方法使用
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    # 定义__getattr__()方法，根据key获取实例属性的value
    # __getattr__()是为了调用**kw关键字参数，通过**kw参数传入的dict不在__dict__属性中，无法直接用self.key调用
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    # 定义__setattr__()方法，可添加和修改实例属性，与__getattr__()方法配套使用
    def __setattr__(self, key, value):
        self[key] = value

    # 定义getValue()方法，实际将调用__getattr__()使用，若没有key值，则返回None
    def getValue(self, key):
        return getattr(self, key, None)

    # 定义getValueOrDefault()方法，根据key获取实例属性，如果没有实例属性，则获取类的默认属性，如果连默认属性也没有，返回None
    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        # getattr()方法是python内置方法，等效于value = self.key，如果没有self.key则value = None
        # 详见https://docs.python.org/3/library/functions.html?highlight=getattr#getattr
        if value is None:
            field = self.__mappings__[key]
            # __mappings__由元类定义，dict类型的类属性合集，其值为field类的实例
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                # 这里很奇怪，Field类中并没有写default()方法，感觉这里是为了扩展default()方法所留下的一个伏笔
                # field.default作为一个属性是不能callable的，所以这里等效于value = field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)
                # python内置方法，详见https://docs.python.org/3/library/functions.html?highlight=getattr#setattr
        return value

    # 由@classmethod修饰的方法为类方法，可以对类属性进行操作，可以继承到子类，当子类使用类方法时clc值将是子类

    # findAll()类方法，在数据库中寻找满足where判断的那一行数据，注意这里where参数要以''字符串形式传入
    # sql语句最终形式类似于：select * from 'table_name' where 'id=1' order by 'id' limit ?
    # 利用args变量传入sql语句中？部分的参数
    @classmethod
    async def findAll(cls, where=None, args=None, **kw):
        ' find objects by where clause. '
        #
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = await select(' '.join(sql), args)
        return [cls(**r) for r in rs]
        # 无法理解这里为什么要这么写，直接写return rs不就行了？
        # cls（**r）for r in rs是一个generator object，所以和协程相关吗？

    # 查找数据库中满足where判断的selectField列，输出该列的元素数目
    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        ' find number by select and where. '
        sql = ['select count(%s) _num_ from `%s`' % (selectField, cls.__table__)]
        # 这里把列名重命名了，相当于select id as _num_，方便后面return
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    # 通过主键（这里是id）来查找数据库中其他内容
    @classmethod
    async def find(cls, pk):
        ' find object by primary key. '
        rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    # 将实例的信息保存到数据库
    async def save(self):
        # 以下两句是把实例的属性值按照__fields__和__primary_key__里的key顺序排列成一个list
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        # 把实例属性insert到数据库
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)
        else:
            logging.info('save operation is successful')

    # 修改数据库数据，通过主键（即id）判断要修改的行
    # 修改时需要给出主键，注意主键是字符串
    async def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows: %s' % rows)

    # 通过主键查找并删除数据库内所有的其他信息
    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warn('failed to remove by primary key: affected rows: %s' % rows)