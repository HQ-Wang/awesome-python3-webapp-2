from models import User
import asyncio
import orm
# import pdb
import time


# 测试插入
async def test_save(loop):
    await orm.create_pool(loop, user='www-data', password='www-data', db='awesome')
    n = 20
    while n < 50:
        u = User(name='test'+str(n), email='test'+str(n)+'@example.com', passwd='hi', image='about:blank')
        await u.save()
        n = n + 1

# 测试查询
async def test_findAll(loop):
    await orm.create_pool(loop, user='www-data', password='www-data', db='awesome')
    # 这里给的关键字参数按照xxx='xxx'的形式给出，会自动分装成dict
    rs = await User.findAll("email='test@example.com'")		# rs是一个元素为dict的list
    # pdb.set_trace()
    for i in range(len(rs)):
        print(rs[i])

# 查询条数
async def test_findNumber(loop):
    await orm.create_pool(loop, user='www-data', password='www-data', db='awesome')
    count = await User.findNumber('email')
    print(count)

# 根据主键查找，这里是id
async def test_find(loop):
    await orm.create_pool(loop, user='www-data', password='www-data', db='awesome')
    # rs是一个dict
    # ID请自己通过数据库查询
    rs = await User.find('001466341638702bd9bacffdd6349069515526e668cb396000')
    print(rs)

# 根据主键删除
async def test_remove(loop):
    await orm.create_pool(loop, user='www-data', password='www-data', db='awesome')
    # 用id初始化一个实例对象
    u = User(id='00146640613070822ee6330fafe42ecaacb762c99edf67b000')
    await u.remove()


# 根据主键更新

async def test_update(loop):
    await orm.create_pool(loop, user='www-data', password='www-data', db='awesome')
    # 必须按照列的顺序来初始化：'update `users` set `created_at`=?, `passwd`=?, `image`=?,
    # `admin`=?, `name`=?, `email`=? where `id`=?' 注意这里要使用time()方法，否则会直接返回个时间戳对象，而不是float值
    u = User(id='001466406164193aecd679b834447d5969107a479eda153000', created_at=time.time(), passwd='test',
             image='about:blank', admin=True, name='admin', email='hello1@example.com')  # id必须和数据库一直，其他属性可以设置成新的值,属性要全
    # pdb.set_trace()
    await u.update()


loop = asyncio.get_event_loop()
loop.run_until_complete(test_save(loop))
__pool = orm.__pool
__pool.close()  # 需要先关闭连接池
loop.run_until_complete(__pool.wait_closed())
loop.close()

