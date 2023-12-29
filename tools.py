from sqlalchemy import create_engine, Column, Integer, String, DateTime, DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.mysql import LONGTEXT
from datetime import datetime
from threading import local
from sqlalchemy.orm import Session, sessionmaker
import time, hashlib, random, json, requests, re, random
from config import User, Password, Ip, Database

# 创建数据库连接
engine = create_engine('mysql+pymysql://%s:%s@%s/%s' % (User, Password, Ip, Database), pool_size=30)

# 创建映射模型
Base = declarative_base()

# 创建线程本地存储对象
local_data = local()


class User(Base):
    """用户表"""
    __tablename__ = "user"
    # 用户id
    id = Column(Integer(), unique=True, primary_key=True, autoincrement=True)
    # 用户名
    name = Column(String(128))
    # 邀请链接
    invite_lj = Column(String(256))
    # 余额
    balance = Column(String(128))
    # 状态
    status = Column(String(96))
    # 第一名字
    firstname = Column(String(96))
    # 注册时间
    time = Column(DateTime(), default=datetime.now())
    # tg的id
    t_id = Column(String(96))
    # 会员标识
    vip = Column(String(96))
    # 拉新人数
    low = Column(Integer(), default=0)
    # 上级邀请码
    parent = Column(String(96))
    # 雷开关 0是开雷，1是关雷，2是随机
    button = Column(String(12), default='2')

    # 将映射与数据库引擎绑定
    __table_args__ = {'mysql_engine': 'InnoDB'}


class Recharge(Base):
    """充值表"""
    __tablename__ = "recharge"
    # id
    id = Column(Integer(), unique=True, primary_key=True, autoincrement=True)
    # 充值金额
    money = Column(String(256))
    # 状态 0失败，1成功，2待支付，3已超时，4已取消
    status = Column(Integer())
    # 转账钱包
    from_address = Column(String(256))
    # 创建时间
    create_time = Column(DateTime(), default=datetime.now())
    # tg的id
    t_id = Column(String(96))
    # 用户id
    user_id = Column(Integer())
    # 第一名字
    firstname = Column(String(96))

    # 将映射与数据库引擎绑定
    __table_args__ = {'mysql_engine': 'InnoDB'}


class Withdrawal(Base):
    """提现表"""
    __tablename__ = "withdrawal"
    # id
    id = Column(Integer(), unique=True, primary_key=True, autoincrement=True)
    # 提现金额
    money = Column(String(256))
    # 创建时间
    create_time = Column(DateTime(), default=datetime.now())
    # tg的id
    t_id = Column(String(96))
    # 操作id
    user_id = Column(Integer())

    # 将映射与数据库引擎绑定
    __table_args__ = {'mysql_engine': 'InnoDB'}


class Record(Base):
    """红包记录表"""
    __tablename__ = "record"
    # id
    id = Column(Integer(), unique=True, primary_key=True, autoincrement=True)
    # 发红包人tg的id
    send_tid = Column(String(96))
    # 发红包人tg的firstname
    firstname = Column(String(96))
    # 红包金额
    money = Column(Integer())
    # 红包倍数
    bei = Column(String(96))
    # 红包包数
    num = Column(Integer())
    # 剩余红包数
    residue = Column(Integer(), default=6)
    # 抢包结果
    result = Column(String(1024))
    # 包主实收
    received = Column(Integer())
    # 盈利
    profit = Column(Integer())
    # 中雷数字
    lei = Column(Integer())
    # 中雷人数
    lei_number = Column(Integer())
    # 创建时间
    create_time = Column(DateTime(), default=datetime.now())
    # 上一次发包时间
    last_fa_time = Column(DateTime(), default=datetime.now())

    # 将映射与数据库引擎绑定
    __table_args__ = {'mysql_engine': 'InnoDB'}


# 抢包记录表
class Snatch(Base):
    """抢红包记录表"""
    __tablename__ = "snatch"
    # id
    id = Column(Integer(), unique=True, primary_key=True, autoincrement=True)
    # 抢红包人的tg的id
    t_id = Column(String(128))
    # 抢红包人的tg的firstname
    firstname = Column(String(256))
    # 抢到的金额
    money = Column(Integer())
    # 发红包人的tg的id
    send_tid = Column(String(128))
    # 抢包时间
    create_time = Column(DateTime(), default=datetime.now())
    # 是否中雷 1.中雷，0.没中雷
    status = Column(Integer())
    # 盈利
    profit = Column(Integer())
    # 对应的红包ID
    r_id = Column(Integer())


class Reward_log(Base):
    """奖励记录表"""
    __tablename__ = "reward_log"
    # id
    id = Column(Integer(), unique=True, primary_key=True, autoincrement=True)
    # 奖励金额
    money = Column(String(128))
    # 奖励类型
    typestr = Column(String(58))
    # 接收奖励的t_id
    t_id = Column(String(256))
    # 创建时间
    create_time = Column(DateTime(), default=datetime.now())


class Return_log(Base):
    """返利记录表"""
    __tablename__ = "return_log"
    # id
    id = Column(Integer(), unique=True, primary_key=True, autoincrement=True)
    # 盈利人的ID
    create_id = Column(String(128))
    # 上级ID
    parent_id = Column(String(128))
    # 抢到的红包金额
    s_money = Column(String(128))
    # 返利金额
    money = Column(String(128))
    # 对应的红包ID
    r_id = Column(Integer())
    # 返利时间
    create_time = Column(DateTime(), default=datetime.now())


class Wallet(Base):
    """钱包记录表"""
    __tablename__ = 'wallet'
    # 订单id
    id = Column(String(68), unique=True, primary_key=True)
    # 订单金额
    money = Column(String(256))
    # 创建时间
    create_time = Column(DateTime())
    # 发起人
    sender = Column(String(256))
    # 接收人
    recipient = Column(String(256))
    # 类型
    typestr = Column(String(48), default="USDT")
    # 插入时间
    insert_time = Column(DateTime(), default=datetime.now())

    # 将映射与数据库引擎绑定
    __table_args__ = {'mysql_engine': 'InnoDB'}


# 拉人记录表
class Holding(Base):
    """拉人记录表"""
    __tablename__ = 'holding'
    # id
    id = Column(Integer(), unique=True, primary_key=True, autoincrement=True)
    # 邀请人
    parent = Column(String(96))
    # 被邀请人
    t_id = Column(String(96))
    # 创建时间
    create_time = Column(DateTime(), default=datetime.now())


# 配置表
class Conf(Base):
    """配置表"""
    __tablename__ = 'conf'
    # id
    id = Column(Integer(), unique=True, primary_key=True, autoincrement=True)
    # 配置名称
    name = Column(String(512))
    # 配置值
    value = Column(LONGTEXT)
    # 值类型
    typestr = Column(String(48))
    # 创建时间
    create_time = Column(DateTime(), default=datetime.now())
    # 备注
    memo = Column(String(512))


# 抽水记录表
class Chou_li(Base):
    """抽水记录表"""
    __tablename__ = 'chou_li'
    # id
    id = Column(Integer(), unique=True, primary_key=True, autoincrement=True)
    # 创建时间
    create_time = Column(DateTime(), default=datetime.now())
    # t_id
    t_id = Column(String(128))
    # 抽水金额
    chou_money = Column(String(128))
    # 红包id
    r_id = Column(Integer())


# 奖金记录表
class Reward_li(Base):
    """奖金记录表"""
    __tablename__ = 'reward_li'
    # id
    id = Column(Integer(), unique=True, primary_key=True, autoincrement=True)
    # 创建时间
    create_time = Column(DateTime(), default=datetime.now())
    # t_id
    t_id = Column(String(128))
    # 奖金金额
    reward_money = Column(String(128))
    # 红包id
    r_id = Column(Integer())
    # 奖励类型
    typestr = Column(String(128))


def get_session():
    if not hasattr(local_data, 'session') or not local_data.session.is_active:
        local_data.session = Session()
    return local_data.session


def timestr_to_time(timestr):
    """时间戳转换为时间字符串"""
    try:
        timestr = int(timestr)
    except Exception as e:
        print(e)
        return 0
    try:
        # 获取年份
        res = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestr))
    except Exception as e:
        return 0
    return res


def md5(target):  # md5加密
    hash_object = hashlib.md5("%$^ASGJZAAss&*(z".encode("utf-8"))
    hash_object.update(target.encode("utf-8"))
    return hash_object.hexdigest()


def get_code():
    now = str(time.time())
    result = now.replace(".", "")
    for i in range(30):
        random_str = random.choice('0123456789abcdefghijklmnopqrstuvwxyzQWERTYUIOPASDFGHJKLZXCVBNM!@#$%^&*()_+')
        result += random_str
    result = result[:30]
    result = md5(result)
    return result


def register(update):
    user_id = update.message.from_user["id"]
    username = update.message.from_user["username"]
    first_name = update.message.from_user["first_name"]
    session = get_session()
    try:
        user = session.query(User).filter_by(t_id=user_id).first()
    except Exception as e:
        print(e)
        print("这里查询出错了！！")
        user = None
    if user:
        return user
    # 生成一个自己的邀请码
    code = get_code()
    try:
        new_user = User(name=username, invite_lj=code, t_id=user_id, firstname=first_name, status=1, balance=0)
        session.add(new_user)
        session.commit()
    except Exception as e:
        session.rollback()
        print(e)
        print("注册失败")
        return None
    return user


def get_order_id():
    now = str(time.time())
    result = now.replace(".", "")
    for i in range(30):
        random_str = random.choice('0123456789abcdefghijklmnopqrstuvwxyzQWERTYUIOPASDFGHJKLZXCVBNM!@#$%^&*()_+')
        result += random_str
    result = result[:30]
    result = md5(result)
    return result


def test_str(name):
    res = re.search(r"\W", str(name))
    if res != None:
        # 有特殊字符
        return 1
    else:
        # 没有特殊字符
        return 0


def find_str(temp):
    if not isinstance(temp, str):
        return 0
    if re.search(r"\s", temp):
        return 1
    elif re.search(r"[\"'<>()\s*()]", temp):
        return 1
    return 0


def distribute_red_packet(total_amount, num_people):
    split_points = sorted(random.sample(range(1, total_amount), num_people - 1))
    amounts = [split_points[0]]
    for i in range(1, num_people - 1):
        amounts.append(split_points[i] - split_points[i - 1])
    amounts.append(total_amount - sum(amounts))

    return amounts


def shunzi3(num):
    num_str = str(num)
    for i in range(len(num_str) - 2):
        if int(num_str[i]) + 1 == int(num_str[i + 1]) and int(num_str[i]) + 2 == int(num_str[i + 2]):
            return True
    return False


def shunzi4(num):
    num_str = str(num)
    for i in range(len(num_str) - 3):  # 修改循环范围为 len(num_str) - 3
        if int(num_str[i]) + 1 == int(num_str[i + 1]) and int(num_str[i]) + 2 == int(num_str[i + 2]) and int(
                num_str[i]) + 3 == int(num_str[i + 3]):
            return True
    return False


def is_baozi3(num):
    num_str = str(num)
    for i in range(len(num_str) - 2):
        if num_str[i] == num_str[i + 1] == num_str[i + 2]:
            return True
    return False


def is_baozi4(num):
    num_str = str(num)
    for i in range(len(num_str) - 3):
        if num_str[i] == num_str[i + 1] == num_str[i + 2] == num_str[i + 3]:
            return True
    return False


# 创建表
Base.metadata.create_all(engine)
# 在映射配置类的最后将数据库引擎与 Base 类绑定
Base.metadata.bind = engine
# 创建会话工厂
Session = sessionmaker(bind=engine)
