from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ParseMode, \
    BotCommand
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext, \
    ChatMemberHandler
import telegram, base64, os, time, requests
from tools import get_session, Record, Recharge, register, User, Session, test_str, find_str, get_code, Holding, \
    distribute_red_packet, Snatch, Return_log, Reward_log, shunzi3, shunzi4, is_baozi3, is_baozi4, Conf, Withdrawal, \
    Chou_li, Wallet, Reward_li
from datetime import datetime, date, timedelta
import random, threading, json
from sqlalchemy import func, Date, cast, Numeric
from sqlalchemy.orm import joinedload
from decimal import Decimal
from config import Text_data, proxy_config

global_data = {}


def qidong():
    global global_data
    from config import config_data
    for line in config_data:
        typestr = line[0]
        name = line[1]
        value = line[2]
        if typestr == "Decimal":
            value = Decimal(value)
        elif typestr == "list":
            value = json.loads(value)
        elif typestr == "int":
            value = int(value)
        elif typestr == "str":
            value = str(value)
        else:
            value = value
        global_data[name] = value

    # 读取数据库配置信息
    session = Session()
    session.expire_all()
    try:
        objs = session.query(Conf).all()
    except Exception as e:
        print(e)
        session.close()
        return
    for obj in objs:
        if obj.typestr == "Decimal":
            value = Decimal(obj.value)
        elif obj.typestr == "list":
            value = json.loads(obj.value)
        elif obj.typestr == "int":
            value = int(obj.value)
        elif obj.typestr == "str":
            value = str(obj.value)
        else:
            value = obj.value
        global_data[obj.name] = value
    session.close()


qidong()
language = global_data["language"]
commands = [
    BotCommand(command="start", description=Text_data[language]["start_com"]),
    BotCommand(command="invite", description=Text_data[language]["create_invite"]),
    BotCommand(command="help", description=Text_data[language]["help_com"]),
    BotCommand(command="recharge", description=Text_data[language]["auto_recharge_btn"]),
    BotCommand(command="wanfa", description=Text_data[language]["wanfa"]),
]
TOKEN = global_data.get("TOKEN")
# updater = Updater(token=TOKEN, use_context=True, request_kwargs=proxy_config)
updater = Updater(token=TOKEN, use_context=True)
updater.bot.set_my_commands(commands)
dispatcher = updater.dispatcher


def get_num():
    a = random.randint(1, 999)
    # 将整数转换为三位数的字符串
    a_str = str(a).zfill(3)
    return a_str


def turn_off(update, context):
    context.bot.delete_message(update.effective_chat.id, message_id=update.callback_query.message.message_id)
    context.bot.answer_callback_query(callback_query_id=update.callback_query.id, text='已关闭！')


# 取消订单
def move_order(update, context):
    kefu = global_data.get("kefu", "toumingde")
    language = global_data.get("language", "cn")
    session = get_session()
    info = update.callback_query.to_dict()
    # tg的id
    t_id = info["from"]["id"]
    try:
        order = session.query(Recharge).filter_by(t_id=t_id, status=2).first()
    except Exception as e:
        print(e)
        context.bot.send_message(update.effective_chat.id, Text_data[language]["turn_order_false"] % kefu)
        session.close()
        return
    if not order:
        context.bot.send_message(update.effective_chat.id, Text_data[language]["order_not_found"] % kefu)
        session.close()
        return
    order.status = 4
    try:
        session.add(order)
        session.commit()
    except Exception as e:
        print(e)
        session.rollback()
        context.bot.send_message(update.effective_chat.id, Text_data[language]["turn_order_false"] % kefu)
        return
    order_id = order.id
    firstname = order.firstname
    create_time = order.create_time
    money = order.money
    content = Text_data[language]["order_move_info"] % (firstname, order_id, create_time, money)
    button = InlineKeyboardButton(Text_data[language]["close"], callback_data="关闭")
    button1 = InlineKeyboardButton(Text_data[language]["again_recharge"], callback_data="再次充值")
    buttons_row = [button, button1]
    keyboard = InlineKeyboardMarkup([buttons_row])
    context.bot.send_message(update.effective_chat.id, content, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    dispatcher.add_handler(CallbackQueryHandler(turn_off, pattern='^关闭$'))
    dispatcher.add_handler(CallbackQueryHandler(recharge, pattern='^再次充值$'))


def listen_order(order_id, chat_id, context):
    now1 = datetime.now()
    print("开始监听的时间为：%s" % str(now1))
    while True:
        session = Session()
        session.expire_all()
        session.commit()
        print("监听订单中 %s" % str(now1))
        language = global_data.get("language", "cn")
        now = datetime.now()
        # 1.查询该订单id
        try:
            order = session.query(Recharge).filter_by(id=order_id).first()
        except Exception as e:
            print(e)
            time.sleep(20)
            continue
        print("查询出的订单状态：%s" % str(order.status))
        # 没有订单数据
        if not order:
            time.sleep(10)
            session.close()
            break
        if order.status == 1:
            # 用户支付成功
            print("订单完成！！")
            context.bot.send_message(chat_id, Text_data[language]["order_recharge_success"])
            context.bot.send_message(global_data.get("Admin_id"), "有新订单充值成功啦！\n时间：%s\n金额：%s\n昵称：%s" % (
                str(now), order.money, order.firstname))
            session.close()
            break
        if order.status == 3:
            print("订单超时！！")
            context.bot.send_message(chat_id, Text_data[language]["order_time_out"])
            session.close()
            break
        if order.status == 4:
            print("订单已取消！！")
            session.close()
            break
        if order.status == 2:
            print("当前订单状态还是待支付！")

            # 判断是否已超时
            if (now - order.create_time).seconds > 600:
                print("订单已超时，现在设置为超时状态！")
                print("订单创建时间为：", order.create_time)
                print("当前时间为：", now)
                order.status = 3
                try:
                    session.add(order)
                    session.commit()
                except Exception as e:
                    print(e)
                    session.rollback()
                    session.close()
                    continue
                context.bot.send_message(chat_id, Text_data[language]["order_time_out"])
                break
        session.close()
        time.sleep(5)

    print("已退出监听订单代码")


def create_order(update, context):
    session = get_session()
    session.expire_all()
    session.commit()
    kefu = global_data.get("kefu", "toumingde")
    language = global_data.get("language", "cn")
    # 我的钱包地址
    myaddress = global_data.get("My_address", "TAZ5gPwfU4bn14dKRqJXbCZJGJMqgoJsaf")
    info = update.callback_query.to_dict()
    # tg的id
    t_id = info["from"]["id"]
    # 1.检测是否存在待支付的订单
    try:
        order = session.query(Recharge).filter_by(status=2, t_id=t_id).first()
    except Exception as e:
        print(e)
        context.bot.send_message(update.effective_chat.id, Text_data[language]["create_order_false"] % kefu)
        return

    if order:
        money = order.money
        create_time = order.create_time

        content = Text_data[language]["create_order_info"] % (myaddress, money, money, money, create_time)
        button = InlineKeyboardButton(Text_data[language]["close"], callback_data="关闭")
        button1 = InlineKeyboardButton(Text_data[language]["move_order"], callback_data="取消订单")
        button2 = InlineKeyboardButton(Text_data[language]["contact_customer"], url="https://t.me/%s" % kefu)
        row = [button, button1, button2]
        keyboard = InlineKeyboardMarkup([row])
        context.bot.send_message(update.effective_chat.id, content, parse_mode=ParseMode.HTML,
                                 reply_markup=keyboard)
        dispatcher.add_handler(CallbackQueryHandler(turn_off, pattern='^关闭'))
        dispatcher.add_handler(CallbackQueryHandler(move_order, pattern='^取消订单$'))
        return

    # 3.用户昵称
    first_name = info["from"]["first_name"]
    # 4.下单时间
    now = datetime.now()
    # 5.创建订单金额
    back_num = get_num()
    print("不存在旧订单，创建新订单！")
    try:
        money = Decimal(update.callback_query.data.replace(" USDT", ".") + back_num)
    except Exception as e:
        print("金额出错了！！")
        return

    content = Text_data[language]["create_order_info"] % (myaddress, money, money, money, str(now))
    button = InlineKeyboardButton(Text_data[language]["close"], callback_data="关闭")
    button1 = InlineKeyboardButton(Text_data[language]["move_order"], callback_data="取消订单")
    button2 = InlineKeyboardButton(Text_data[language]["contact_customer"], url="https://t.me/%s" % kefu)
    row = [button, button1, button2]
    keyboard = InlineKeyboardMarkup([row])

    try:
        user = session.query(User).filter_by(t_id=t_id).first()
    except Exception as e:
        context.bot.send_message(update.effective_chat.id, Text_data[language]["create_order_false"] % kefu)
        session.close()
        return
    if not user:
        context.bot.send_message(update.effective_chat.id, Text_data[language]["create_order_false"] % kefu)
        session.close()
        return

    # 将订单入库
    try:
        order = Recharge(status=2, from_address=myaddress, t_id=t_id, money=money, user_id=1, firstname=first_name,
                         create_time=now)
        session.add(order)
        session.commit()
    except Exception as e:
        print("订单入库失败")
        session.rollback()
        context.bot.send_message(update.effective_chat.id, Text_data[language]["create_order_false"] % kefu)
        session.close()
        return
    context.bot.send_message(update.effective_chat.id, content, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    dispatcher.add_handler(CallbackQueryHandler(turn_off, pattern='^关闭$'))
    dispatcher.add_handler(CallbackQueryHandler(move_order, pattern='^取消订单$'))

    # 开启另一个线程，监听订单完成与否，，出发发送消息至客户中
    t1 = threading.Thread(target=listen_order, args=(order.id, update.effective_chat.id, context))
    t1.start()
    session.close()


def recharge(update, context):
    Group_id = global_data.get("Group_id")
    kefu = global_data.get("kefu", "toumingde")
    language = global_data.get("language", "cn")
    if Group_id == str(update.effective_chat.id):
        message_id = update.message.message_id
        context.bot.send_message(update.effective_chat.id, Text_data[language]["recharge_tips"],
                                 reply_to_message_id=message_id)
        return

    button0 = InlineKeyboardButton('30 USDT', callback_data='30 USDT')
    button1 = InlineKeyboardButton('100 USDT', callback_data='100 USDT')
    button2 = InlineKeyboardButton('200 USDT', callback_data='200 USDT')
    row1 = [button0, button1, button2]
    button3 = InlineKeyboardButton('500 USDT', callback_data="500 USDT")
    button4 = InlineKeyboardButton('1000 USDT', callback_data="1000 USDT")
    button5 = InlineKeyboardButton('2000 USDT', callback_data='2000 USDT')
    row2 = [button3, button4, button5]
    button6 = InlineKeyboardButton(Text_data[language]["close"], callback_data="关闭")
    button7 = InlineKeyboardButton(Text_data[language]["contact_customer"], url="https://t.me/%s" % kefu)
    row3 = [button6, button7]

    keyboard = InlineKeyboardMarkup([row1, row2, row3])

    context.bot.send_message(update.effective_chat.id, Text_data[language]["recharge_info"] % kefu,
                             reply_markup=keyboard)

    dispatcher.add_handler(CallbackQueryHandler(create_order, pattern='^\d{1,} USDT$'))
    dispatcher.add_handler(CallbackQueryHandler(turn_off, pattern='^关闭$'))


def rob(update, context):
    Group_id = global_data.get("Group_id")
    language = global_data.get("language", "cn")
    Bei = Decimal(global_data.get("Bei"))
    Num = global_data.get("Num")
    Chou = Decimal(global_data.get("Chou"))
    Dai_chou = Decimal(global_data.get("Dai_chou"))
    info = update.callback_query.to_dict()
    user_id = info["from"]["id"]
    first_name = info["from"].get("first_name")
    username = info["from"].get("username")
    Balance_first = global_data.get("Balance", "3000")
    query = update.callback_query
    chat_id = query.message.chat.id
    message_id = query.message.message_id
    callback_data = query.data
    session = Session()
    session.expire_all()
    session.commit()
    try:
        user = session.query(User).filter_by(t_id=user_id).first()
    except Exception as e:
        query.answer(Text_data["rob_false"], show_alert=True)
        session.close()
        return
    if not user:
        parent = ""
        code = get_code()
        try:
            user = User(name=username, invite_lj=code, t_id=user_id, firstname=first_name, status=1,
                        balance=Balance_first,
                        parent=parent)
            session.add(user)
            session.flush()
        except Exception as e:
            print(e)
            session.close()
            return
    info = callback_data.split("_")
    r_id = int(info[1])
    money = int(info[2])
    lei = int(info[3])
    # num = int(info[4])
    # 1.校验红包是否存在
    try:
        record = session.query(Record).get(r_id)
    except Exception as e:
        print(e)
        session.close()
        # 红包已被抢完
        return
    if not record:
        session.close()
        return
    # 3.校验是否抢过红包
    try:
        tmp = session.query(Snatch).filter_by(r_id=r_id, t_id=user_id).first()
    except Exception as e:
        query.answer(Text_data[language]["rob_false"], show_alert=True)
        session.close()
        return
    if tmp:
        try:
            query.answer(Text_data[language]["had_rob"], show_alert=True)
        except Exception as e:
            pass
        session.close()
        return
    # 校验余额
    if Decimal(user.balance) < money * 100 * Bei:
        query.answer(Text_data[language]["account_error"] % round(money * Bei, 2), show_alert=True)
        session.close()
        return

    # 2.校验红包是否被抢完
    if record.residue <= 0:
        query.answer(Text_data[language]["red_envelope_empty"], show_alert=True)
        session.close()
        # 红包已被抢完
        return
    try:
        record = session.query(Record).with_for_update(read=False).get(r_id)
    except Exception as e:
        print(e)
        session.rollback()
        session.close()
        # 红包已被抢完
        return
    num = record.residue
    # 4.获取抢到的红包金额
    result = json.loads(record.result)
    s_money = result[record.residue - 1]
    print("恭喜抢到的红包金额为：", s_money)
    # 5.红包数量减一
    record.residue -= 1
    try:
        session.add(record)
        session.commit()
    except Exception as e:
        session.rollback()
        session.close()
        print(e)
        query.answer(Text_data[language]["rob_false"], show_alert=True)
        return
    try:
        sender = session.query(User).filter_by(t_id=record.send_tid).first()
    except Exception as e:
        print(e)
        session.rollback()
        query.answer(Text_data[language]["rob_false"], show_alert=True)
        session.close()
        return
    if not sender:
        session.rollback()
        query.answer(Text_data[language]["rob_false"], show_alert=True)
        session.close()
        return
    con = Text_data[language]["no_lei"]
    if str(s_money)[-1] == str(lei):
        con = Text_data[language]["lei"]

    try:
        query.answer(Text_data[language]["snatch_line"] % ((s_money / 100), con, (Decimal(user.balance) / 100)),
                     show_alert=True)
    except Exception as e:
        session.rollback()
        query.answer(Text_data[language]["rob_false"], show_alert=True)
        session.close()
        return

    # 6.判断是否中雷和盈利金额（可为负数）
    if str(s_money)[-1] == str(lei):
        # 要给发包人加余额
        n_status = 1
        con = Text_data[language]["lei"]
        profit = -(Bei * money * 100)
        lose = Bei * money * 100
        # 本身余额 + 中雷获取的奖金 - 利息
        sender.balance = str(
            int(Decimal(sender.balance) + Decimal(money * 100 * Bei) - int((money * 100 * Bei) * Chou)))
        try:
            chou_obj_lei = Chou_li(t_id=user_id, chou_money=str(Decimal(money * 100 * Bei * Chou)), r_id=r_id,
                                   create_time=datetime.now())
        except Exception as e:
            session.rollback()
            query.answer(Text_data[language]["rob_false"], show_alert=True)
            session.close()
            return
        session.add(chou_obj_lei)
        session.add(sender)
        if sender.parent:
            # 计算返利
            try:
                shangji = session.query(User).filter_by(invite_lj=sender.parent).first()
            except Exception as e:
                shangji = ""
            if shangji:
                shangji.balance = int(Decimal(shangji.balance)) + int(int(money * 100 * Chou) * Dai_chou)
                session.add(shangji)
                try:
                    f_obj = Return_log(create_id=sender.id, parent_id=shangji.id,
                                       money=int(int(money * 100 * Bei * Chou) * Dai_chou),
                                       r_id=record.id, s_money=s_money)
                    session.add(f_obj)
                except Exception as e:
                    print(e)
                    print("统计返利失败")
    else:
        n_status = 0
        con = Text_data[language]["no_lei"]
        profit = s_money
        lose = 0

    # 送奖励
    if str(s_money)[-2:0] == "00":
        tmp_money = s_money / 100
    else:
        tmp_money = s_money
    reward = 0
    if shunzi3(tmp_money):
        if shunzi4(tmp_money):
            context.bot.send_message(chat_id=Group_id,
                                     text=Text_data[language]["big_shunzi"] % first_name,
                                     parse_mode=ParseMode.HTML)
            reward = 5888
            typestr = "大顺子"
        else:
            context.bot.send_message(chat_id=Group_id,
                                     text=Text_data[language]["small_shunzi"] % first_name,
                                     parse_mode=ParseMode.HTML)
            reward = 588
            typestr = "小顺子"
        if reward:
            reward_obj = Reward_li(reward_money=str(reward), t_id=user_id, r_id=r_id, create_time=datetime.now(),
                                   typestr=typestr)
            session.add(reward_obj)

    user.balance = Decimal(user.balance) + reward
    reward = 0
    if is_baozi3(tmp_money):
        if is_baozi4(tmp_money):
            context.bot.send_message(chat_id=Group_id,
                                     text=Text_data[language]["big_baozi"] % first_name,
                                     parse_mode=ParseMode.HTML)
            reward = 5888
            typestr = "大豹子"
        else:
            context.bot.send_message(chat_id=Group_id,
                                     text=Text_data[language]["small_baozi"] % first_name,
                                     parse_mode=ParseMode.HTML)
            reward = 588
            typestr = "大豹子"
        if reward:
            reward_obj = Reward_li(reward_money=str(reward), t_id=user_id, r_id=r_id, create_time=datetime.now(),
                                   typestr=typestr)
            session.add(reward_obj)
    user.balance = Decimal(user.balance) + reward
    # 需要扣掉2.5%的利息
    # 本身余额 + 抢包金额 - 利息 -（如果中雷了，需要扣金额的1.8倍）
    # print("抢包者当前余额为：", user.balance)
    user.balance = str(int(Decimal(user.balance) + s_money - int(s_money * Chou) - lose))
    # print("抢包者扣除利息为：", int(s_money * Chou))
    # print("抢包者结算后余额为：", user.balance)
    try:
        chou_obj = Chou_li(t_id=user_id, chou_money=str(Decimal(s_money * Chou)), r_id=r_id, create_time=datetime.now())
    except Exception as e:
        session.rollback()
        query.answer(Text_data[language]["rob_false"], show_alert=True)
        session.close()
        return
    session.add(chou_obj)
    # 添加抢红包记录
    try:
        s_obj = Snatch(t_id=user_id, money=s_money, send_tid=record.send_tid, status=n_status, profit=profit, r_id=r_id,
                       firstname=first_name, create_time=datetime.now())
    except Exception as e:
        session.rollback()
        query.answer(Text_data[language]["rob_false"], show_alert=True)
        session.close()
        return
    try:
        session.add(s_obj)
        session.add(user)
        session.commit()
    except Exception as e:
        print(e)
        session.rollback()
        session.close()
        query.answer(Text_data[language]["rob_false"], show_alert=True)
        return
    if record.residue == 0:
        new_text = Text_data[language]["settle_rob_order"] % (record.firstname, money, Num, Bei, lei)
        icon_dic = {"1": "💣", "0": "💵"}
        # 查询出该记录的所有抢包结果
        try:
            objs = session.query(Snatch).filter_by(r_id=record.id).all()
        except Exception as e:
            session.rollback()
            session.close()
            query.answer(Text_data[language]["rob_false"], show_alert=True)
            return
        flag = 1
        # 总盈利
        total = 0
        # 包主实收
        for line in objs:
            # 金额
            l_money = line.money
            # 昵称
            firstname = line.firstname
            # 状态
            status = line.status
            # 盈利
            profit = line.profit
            if profit < 0:
                # 说明包主盈利了
                total += abs(profit)
            new_text += "%s.[%s]-%s U  %s\n" % (
                flag, icon_dic.get(str(status)), "%.2f" % float(int(l_money) / 100), firstname)
            flag += 1
        if n_status:
            # 最后一个中雷了
            total += money * Bei * 100
        record.profit = (total / 100)
        record.received = ((total / 100) - money)
        new_text += "%s.[%s]-%s U  %s\n" % (
            flag, icon_dic.get(str(n_status)), "%.2f" % float(int(s_money) / 100), first_name)
        new_text += Text_data[language]["rob_packet_body"] % ((total / 100), money, round(((total / 100) - money), 2))
        try:
            session.add(s_obj)
            session.add(record)
            session.add(user)
            session.commit()
        except Exception as e:
            print(e)
            session.rollback()
            session.close()
            query.answer(Text_data[language]["rob_false"], show_alert=True)
            return
        # 获取原始消息中的 InlineKeyboardMarkup 对象
        old_keyboard = query.message.reply_markup
        # 合并新的按钮行和其他行为新的键盘对象
        new_keyboard = InlineKeyboardMarkup(old_keyboard.inline_keyboard[1:])

        context.bot.edit_message_caption(chat_id, message_id=message_id, caption=new_text, reply_markup=new_keyboard,
                                         parse_mode=ParseMode.HTML)
        query.answer(Text_data[language]["snatch_line"] % ((s_money / 100), con, (Decimal(user.balance) / 100)),
                     show_alert=True)
    else:
        try:
            session.add(s_obj)
            session.add(record)
            session.add(user)
            session.commit()
        except Exception as e:
            print(e)
            session.rollback()
            session.close()
            query.answer(Text_data[language]["rob_false"], show_alert=True)
            return

        # 获取原始消息中的 InlineKeyboardMarkup 对象
        old_keyboard = query.message.reply_markup

        # 更新 rob_btn 的内容
        # rob_btn = InlineKeyboardButton(Text_data[language]["rob_button"] % (Num, num, money, lei),
        #                                callback_data='rob_%s_%s_%s_%s' % (r_id, money, lei, num + 1))
        rob_btn = InlineKeyboardButton(Text_data[language]["rob_button"] % (Num, Num - num + 1, money, lei),
                                       callback_data='rob_%s_%s_%s_%s' % (r_id, money, lei, Num - num + 2))

        # 将新的按钮添加到新的按钮行中
        new_buttons_row1 = [rob_btn]

        # 合并新的按钮行和其他行为新的键盘对象
        new_keyboard = InlineKeyboardMarkup([new_buttons_row1] + old_keyboard.inline_keyboard[1:])

        # 更新消息的键盘
        try:
            query.edit_message_reply_markup(reply_markup=new_keyboard)
        except Exception as e:
            pass

    dispatcher.add_handler(CallbackQueryHandler(alert, pattern='^promote_query'))
    dispatcher.add_handler(CallbackQueryHandler(yue, pattern='^yue'))
    dispatcher.add_handler(CallbackQueryHandler(rob, pattern='^rob_%s_%s_%s_%s' % (r_id, money, lei, Num - num + 2)))
    session.close()


def kailei(update, context):
    info = update.callback_query.to_dict()

    user_id = info["from"]["id"]
    query = update.callback_query

    callback_data = query.data
    session = Session()
    session.expire_all()
    session.commit()

    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li:
        print(user_id)
        return

    info = callback_data.split("_")
    t_id = int(info[1])
    status = int(info[2])
    s_dic = {"1": "出雷", "0": "没雷", "2": "随机"}
    if status not in [0, 1, 2]:
        query.answer("设置出错", show_alert=True)
        return

    try:
        user = session.query(User).filter_by(t_id=t_id).first()
    except Exception as e:
        print(e)
        query.answer("设置出错", show_alert=True)
        session.close()
        return
    user.button = status
    try:
        session.add(user)
        session.commit()
    except Exception as e:
        print(e)
        query.answer("设置出错", show_alert=True)
        session.close()
        return
    query.answer("设置成功，当前用户：%s，状态为：%s" % (t_id, s_dic.get(str(status))), show_alert=True)


def today_record(update, context):
    New_reward = global_data.get("New_reward")
    language = global_data.get("language", "cn")
    Chou = float(global_data.get("Chou"))
    Dai_chou = float(global_data.get("Dai_chou"))
    info = update.callback_query.to_dict()
    first_name = info["from"].get("first_name")
    query = update.callback_query
    chat_id = query.message.chat.id
    info = update.callback_query.to_dict()
    t_id = info["from"]["id"]
    today = datetime.now().date()
    session = Session()
    session.expire_all()
    session.commit()
    print("用户id为：%s" % t_id)
    try:
        user = session.query(User).filter_by(t_id=t_id).first()
    except Exception as e:
        print(e)
        query.answer(Text_data[language]["search_false"], show_alert=True)
        session.close()
        return
    if not user:
        if not user:
            query.answer(Text_data[language]["search_false"], show_alert=True)
            session.close()
            return
    user_id = user.id

    try:
        r_objs = session.query(Record).filter(Record.send_tid == user.t_id,
                                              func.cast(Record.create_time, Date) == today).all()
    except Exception as e:
        print(e)
        query.answer(Text_data[language]["search_false"], show_alert=True)
        session.close()
        return
    # 发包支出
    zhichu = 0
    # 发包盈利
    yingli = 0
    for robj in r_objs:
        if robj.money:
            # 发包金额
            zhichu += robj.money / 100
        if robj.profit:
            # 发包盈利
            yingli += robj.profit

    # 我发包玩家中雷上级代理抽成
    lei_chou = 0
    # 我发包玩家中雷平台抽成
    pingtai_chou = 0
    try:
        sn_objs = session.query(Snatch).filter(Snatch.send_tid == user.t_id,
                                               func.cast(Snatch.create_time, Date) == today, Snatch.status == 1).all()
    except Exception as e:
        print(e)
        query.answer(Text_data[language]["search_false"], show_alert=True)
        session.close()
        return
    for sn_obj in sn_objs:
        if user.parent:
            # # 得判断这个用户有没有上级
            lei_chou += (abs(sn_obj.profit) / 100) * Chou * Dai_chou
        pingtai_chou += (abs(sn_obj.profit) / 100) * Chou

    # 抢包收入
    snatch_shou = 0
    # 抢包中雷赔付
    snatch_lei_lose = 0
    try:
        sn_objs = session.query(Snatch).filter(Snatch.t_id == user.t_id,
                                               func.cast(Snatch.create_time, Date) == today).all()
    except Exception as e:
        print(e)
        query.answer(Text_data[language]["search_false"], show_alert=True)
        session.close()
        return
    for sn_obj in sn_objs:
        # 抢包收入
        snatch_shou += (sn_obj.money / 100)
        if sn_obj.status == 1:
            # 抢包中雷赔付
            snatch_lei_lose += (abs(sn_obj.profit) / 100)

    # 邀请返利
    invite_money = 0
    try:
        in_objs = session.query(Holding).filter(Holding.parent == user.t_id,
                                                func.cast(Holding.create_time, Date) == today).all()
    except Exception as e:
        print(e)
        query.answer(Text_data[language]["search_false"], show_alert=True)
        session.close()
        return
    invite_money += len(in_objs) * (New_reward / 100)

    # 下级中雷返点
    try:
        logs = session.query(Return_log).filter(Return_log.create_id == user_id,
                                                func.cast(Return_log.create_time, Date) == today).all()
    except Exception as e:
        print(e)
        query.answer(Text_data[language]["search_false"], show_alert=True)
        session.close()
        return
    low_lei_fan = 0
    for log in logs:
        low_lei_fan += int(log.money)

    try:
        total_reward = session.query(func.sum(cast(Reward_li.reward_money, Numeric))).filter(
            Reward_li.t_id == t_id).first()
    except Exception as e:
        print(e)
        return
    if not total_reward[0]:
        total_reward = [0]
    try:
        total_reward = round((total_reward[0] / 100), 2)
    except Exception:
        return

    content = Text_data[language]["today_record"] % (
        user.t_id, zhichu, yingli, round(lei_chou, 2), round(pingtai_chou, 2), round(snatch_shou, 2),
        round(snatch_lei_lose, 2), invite_money, round(low_lei_fan, 2), total_reward)
    # query.answer(content, show_alert=True)
    try:
        context.bot.send_message(chat_id=t_id, text=content, parse_mode=ParseMode.HTML)
        query.answer(Text_data[language]["today_text_info"], show_alert=True)
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text=Text_data[language]["today_record_false"] % first_name,
                                 parse_mode=ParseMode.HTML)


def alert(update, context):
    language = global_data.get("language", "cn")
    session = Session()
    session.expire_all()
    # 用户id
    info = update.callback_query.to_dict()
    user_id = info["from"]["id"]
    query = update.callback_query
    # 根据ID查询邀请数据
    try:
        # 累计邀请
        count = session.query(Holding).filter_by(parent=user_id).count()
    except Exception as e:
        print(e)
        query.answer(Text_data[language]["search_false"], show_alert=True)
        session.close()
        return
    if not count:
        count = 0
    try:
        # 最新十条记录
        records = session.query(Holding).filter_by(parent=user_id).order_by(Holding.create_time.desc()).limit(10).all()
    except Exception as e:
        print(e)
        query.answer(Text_data[language]["search_false"], show_alert=True)
        session.close()
        return
    content = Text_data[language]["invite_info"] % (user_id, count)
    for obj in records:
        # 被邀请人ID
        t_id = obj.t_id
        # 邀请时间
        create_time = str(obj.create_time)[:10]
        content += Text_data[language]["invite_line"] % (create_time, t_id)
    query.answer(content, show_alert=True)


# 查看余额
def yue(update, context):
    session = Session()
    session.expire_all()
    info = update.callback_query.to_dict()
    user_id = info["from"].get("id")
    language = global_data.get("language", "cn")
    # 在这里添加你的回调逻辑
    query = update.callback_query
    # 根据ID查询邀请数据
    try:
        user = session.query(User).filter_by(t_id=user_id).first()
    except Exception as e:
        print(e)
        session.close()
        query.answer(Text_data[language]["search_false"], show_alert=True)
        return
    if not user:
        session.close()
        query.answer(Text_data[language]["user_not_found"], show_alert=True)
        return
    fistname = user.firstname
    name = user.name
    balance = Decimal(user.balance) / 100
    content = Text_data[language]["my_money"] % (fistname, name, user_id, balance)
    query.answer(content, show_alert=True)


def start(update, context):
    Group_name = global_data.get("Group_name")
    language = global_data.get("language", "cn")
    Channel_name = global_data.get("Channel_name")
    New_reward = global_data.get("New_reward")
    user_id = update.message.from_user["id"]
    username = update.message.from_user["username"]
    first_name = update.message.from_user["first_name"]
    Balance_first = global_data.get("Balance", "0")
    chat_id = update.message.chat_id
    button = InlineKeyboardButton(Text_data[language]["official_group"], url="https://t.me/%s" % Group_name)
    button1 = InlineKeyboardButton(Text_data[language]["official_channel"], url="https://t.me/%s" % Channel_name)
    buttons_row = [button, button1]
    keyboard = InlineKeyboardMarkup([buttons_row])
    context.bot.send_message(chat_id=chat_id, text=Text_data[language]["welcome_user"] % user_id,
                             reply_markup=keyboard, parse_mode=ParseMode.HTML)
    # 获取 /start 命令的参数
    args = context.args
    if args:
        parent = args[0]
    else:
        parent = ""
    # 判断是否是新用户
    session = Session()
    session.expire_all()
    session.commit()
    try:
        user = session.query(User).filter_by(t_id=user_id).first()
    except Exception as e:
        print(e)
        user = None
    if user:
        return

    if test_str(parent) or find_str(parent):
        return
    # 生成一个自己的邀请码
    code = get_code()
    try:
        new_user = User(name=username, invite_lj=code, t_id=user_id, firstname=first_name, status=1,
                        balance=Balance_first,
                        parent=parent)
        session.add(new_user)
        session.flush()
    except Exception as e:
        session.close()
        return
    # 给上级送奖励
    try:
        p_user = session.query(User).filter_by(invite_lj=parent).first()
    except Exception as e:
        session.close()
        p_user = ""
    if p_user:
        p_user.low += 1
        # 拉新奖励
        p_user.balance = Decimal(p_user.balance) + New_reward
        # 添加拉新记录
        try:
            obj = Holding(parent=p_user.t_id, t_id=user_id)
        except Exception as e:
            obj = ""

        session.add(p_user)
        if obj:
            session.add(obj)
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        session.close()
        return
    session.close()


def send_help(update, context):
    Channel_name = global_data.get("Channel_name", "yingsheng001")
    Bot_name = global_data.get("Bot_name", "yinghai_bot")
    language = global_data.get("language", "cn")
    kefu = global_data.get("kefu", "toumingde")
    caiwu = global_data.get("caiwu", "touminde")
    chat_id = update.message.chat_id
    content = Text_data[language]["help_info"]
    button = InlineKeyboardButton(Text_data[language]["kefu"], url="https://t.me/%s" % kefu)
    button1 = InlineKeyboardButton(Text_data[language]["recharge"], url="https://t.me/%s" % caiwu)
    button2 = InlineKeyboardButton(Text_data[language]["wanfa"], url="https://t.me/%s" % Channel_name)
    button3 = InlineKeyboardButton(Text_data[language]["balance"], callback_data="yue")
    # 将四个按钮放在一个列表中作为一行的按钮列表
    buttons_row = [button, button1, button2, button3]
    button4 = InlineKeyboardButton(Text_data[language]["tuiguang_search"], callback_data="promote_query")
    button5 = InlineKeyboardButton(Text_data[language]["today_record_btn"], callback_data="today_record")
    buttons_row2 = [button4, button5]
    keyboard = InlineKeyboardMarkup([buttons_row, buttons_row2])
    dispatcher.add_handler(CallbackQueryHandler(alert, pattern='^promote_query'))
    dispatcher.add_handler(CallbackQueryHandler(today_record, pattern='^today_record'))
    dispatcher.add_handler(CallbackQueryHandler(yue, pattern='^yue'))
    context.bot.send_message(chat_id=chat_id, text=content, reply_markup=keyboard)


def invite(update, context):
    user_id = update.message.from_user.id
    Bot_name = global_data.get("Bot_name")
    language = global_data.get("language", "cn")
    username = update.message.from_user["username"]
    Balance_first = global_data.get("Balance", "3000")
    first_name = update.message.from_user["first_name"]
    session = Session()
    session.expire_all()
    session.commit()
    try:
        user = session.query(User).filter_by(t_id=user_id).first()
    except Exception as e:
        print(e)
        user = None
    if not user:
        # 生成一个自己的邀请码
        code = get_code()
        try:
            user = User(name=username, invite_lj=code, t_id=user_id, firstname=first_name, status=1,
                        balance=Balance_first)
            session.add(user)
            session.flush()
        except Exception as e:
            print(e)
            session.rollback()
            session.close()
            return
    invite_lj = user.invite_lj
    invite_link = f"https://t.me/%s?start=%s" % (Bot_name, invite_lj)
    update.message.reply_text(Text_data[language]["invite_link"] % invite_link)


def wanfa(update, context):
    Channel_name = global_data.get("Channel_name", "yingsheng001")
    Bot_name = global_data.get("Bot_name", "yinghai_bot")
    language = global_data.get("language", "cn")
    kefu = global_data.get("kefu", "toumingde")
    caiwu = global_data.get("caiwu", "toumingde")
    chat_id = update.message.chat_id
    content = Text_data[language]["wanfa_info"]
    button = InlineKeyboardButton(Text_data[language]["kefu"], url="https://t.me/%s" % kefu)
    button1 = InlineKeyboardButton(Text_data[language]["recharge"], url="https://t.me/%s" % caiwu)
    button2 = InlineKeyboardButton(Text_data[language]["wanfa"], url="https://t.me/%s" % Channel_name)
    button3 = InlineKeyboardButton(Text_data[language]["balance"], callback_data="yue")
    # 将四个按钮放在一个列表中作为一行的按钮列表
    buttons_row = [button, button1, button2, button3]
    button4 = InlineKeyboardButton(Text_data[language]["tuiguang_search"], callback_data="promote_query")
    button5 = InlineKeyboardButton(Text_data[language]["today_record_btn"], callback_data="today_record")
    buttons_row2 = [button4, button5]
    keyboard = InlineKeyboardMarkup([buttons_row, buttons_row2])
    dispatcher.add_handler(CallbackQueryHandler(alert, pattern='^promote_query'))
    dispatcher.add_handler(CallbackQueryHandler(today_record, pattern='^today_record'))
    dispatcher.add_handler(CallbackQueryHandler(yue, pattern='^yue'))
    context.bot.send_message(chat_id=chat_id, text=content, reply_markup=keyboard)


def adminrecharge(update, context):
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")
    language = global_data.get("language")
    # 获取传递的参数
    args = context.args
    if str(user_id) not in Admin_li:
        print(user_id)
        return
    if not args:
        context.bot.send_message(chat_id=chat_id, text="模板为：/adminrecharge 用户id 充值金额")
        return
    # 处理参数逻辑，这里只是简单地将参数打印出来
    for arg in args:
        try:
            arg = int(arg)
        except Exception as e:
            return
    t_id = args[0]
    money = int(args[1])
    if len(args) > 2:
        return
    session = Session()
    session.expire_all()
    try:
        user = session.query(User).filter_by(t_id=t_id).first()
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=chat_id, text="数据库出错")
        session.close()
        return
    print("要充值的金额为：", money)
    if money < 5 or money > 50000:
        context.bot.send_message(chat_id=chat_id, text="充值金额最少5U，最高5万U！")
        session.close()
        return
    user.balance = Decimal(user.balance) + Decimal(money * 100)
    # 添加充值记录

    try:
        r_obj = Recharge(t_id=t_id, status=1, create_time=datetime.now(), user_id=user.id, firstname=user.firstname,
                         money=money)
        session.add(r_obj)
        session.add(user)
        session.commit()
    except Exception as e:
        print(e)
        session.rollback()
        session.close()
        context.bot.send_message(chat_id=chat_id, text="充值失败")
        return
    context.bot.send_message(chat_id=chat_id,
                             text="用户：%s\ntg：%s\n充值金额：%s\n状态：成功\n账户余额为：%s" % (
                                 user.firstname, t_id, money, round(Decimal(user.balance) / 100, 2)))
    context.bot.send_message(chat_id=t_id,
                             text=Text_data[language]["recharge_arrival"] % (user.firstname, money),
                             parse_mode=ParseMode.HTML)
    session.close()


def add_admin(update, context):
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_id = global_data.get("Admin_id")
    # 获取传递的参数
    args = context.args
    if str(user_id) != Admin_id:
        print(user_id)
        return
    if not args:
        context.bot.send_message(chat_id=chat_id, text="模板为：/add ID")
        return
    try:
        t_id = int(args[0])
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=chat_id, text="ID不合法")
        return
    session = Session()
    session.expire_all()
    session.commit()
    try:
        c_obj = session.query(Conf).filter_by(name='Admin_li').first()
    except Exception as e:
        print(e)
        session.close()
        context.bot.send_message(chat_id=chat_id, text="添加管理员出错！")
        return
    if not c_obj:
        # 数据库没有这条记录，则添加一条
        try:
            c_obj = Conf(name="Admin_li", value=json.dumps([str(t_id)]), typestr="list", create_time=datetime.now(),
                         memo="管理员列表")
        except Exception as e:
            context.bot.send_message(chat_id=chat_id, text="添加管理员出错！")
            session.close()
            return
        global_data["Admin_li"] = [str(t_id)]
    else:
        Admin_li = json.loads(c_obj.value)
        if str(t_id) in Admin_li:
            context.bot.send_message(chat_id=chat_id, text="该ID管理员已在列表中!")
            session.close()
            return
        Admin_li.append(str(t_id))
        global_data["Admin_li"] = Admin_li
        c_obj.value = json.dumps(Admin_li)
    try:
        session.add(c_obj)
        session.commit()
    except Exception as e:
        session.rollback()
        session.close()
        print(e)
        context.bot.send_message(chat_id=chat_id, text="添加管理员出错！")
        return
    context.bot.send_message(chat_id=chat_id, text="添加管理员成功！")
    session.close()


def del_admin(update, context):
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_id = global_data.get("Admin_id")
    # 获取传递的参数
    args = context.args
    if str(user_id) != Admin_id:
        print(user_id)
        return
    if not args:
        context.bot.send_message(chat_id=chat_id, text="模板为：/del ID")
        return
    try:
        t_id = int(args[0])
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=chat_id, text="ID不合法")
        return
    session = Session()
    session.expire_all()
    session.commit()
    try:
        c_obj = session.query(Conf).filter_by(name='Admin_li').first()
    except Exception as e:
        print(e)
        session.close()
        context.bot.send_message(chat_id=chat_id, text="删除管理员出错！")
        return
    if not c_obj:
        context.bot.send_message(chat_id=chat_id, text="没有该管理员信息！")
        session.close()
        return
    else:
        Admin_li = json.loads(c_obj.value)
        Admin_li.remove(str(t_id))
        global_data["Admin_li"] = Admin_li
        c_obj.value = json.dumps(Admin_li)
    try:
        session.add(c_obj)
        session.commit()
    except Exception as e:
        session.rollback()
        session.close()
        print(e)
        context.bot.send_message(chat_id=chat_id, text="删除管理员出错！")
        return
    context.bot.send_message(chat_id=chat_id, text="删除管理员成功！")
    session.close()


def admin_list(update, context):
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li:
        print(user_id)
        return

    session = Session()
    session.expire_all()
    session.commit()
    try:
        c_obj = session.query(Conf).filter_by(name='Admin_li').first()
    except Exception as e:
        print(e)
        session.close()
        context.bot.send_message(chat_id=chat_id, text="查询管理员列表出错！")
        return
    if not c_obj:
        context.bot.send_message(chat_id=chat_id, text="系统没有普通管理员信息！")
        session.close()
        return
    Admin_li = json.loads(c_obj.value)
    text = ""
    for admin in Admin_li:
        text += "<code>%s</code>\n" % admin

    context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
    session.close()


def xiafen(update, context):
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")
    # 获取传递的参数
    args = context.args
    if str(user_id) not in Admin_li:
        print(user_id)
        return
    if not args:
        context.bot.send_message(chat_id=chat_id, text="模板为：/xf 用户id 下分金额")
        return
    # 处理参数逻辑，这里只是简单地将参数打印出来
    for arg in args:
        try:
            arg = int(arg)
        except Exception as e:
            return
    t_id = args[0]
    money = int(args[1])
    if len(args) > 2:
        return
    session = Session()
    session.expire_all()
    try:
        user = session.query(User).filter_by(t_id=t_id).first()
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=chat_id, text="数据库出错")
        session.close()
        return
    print("要下分的金额为：", money)
    if money < 30 or money > 50000:
        context.bot.send_message(chat_id=chat_id, text="下分金额最少30U，最高5万U！")
        session.close()
        return
    # 校验流水是否满足

    user.balance = Decimal(user.balance) - Decimal(money * 100)
    try:
        w_obj = Withdrawal(user_id=user.id, t_id=t_id, money=money)
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=chat_id, text="下分失败，请联系技术人员！")
        session.close()
        return
    try:
        session.add(w_obj)
        session.add(user)
        session.commit()
    except Exception as e:
        print(e)
        session.rollback()
        session.close()
        context.bot.send_message(chat_id=chat_id, text="下分失败！")
        return
    context.bot.send_message(chat_id=chat_id,
                             text="用户：%s\ntg：%s\n下分金额：%s\n状态：成功\n账户余额为：%s" % (
                                 user.firstname, t_id, money, round(Decimal(user.balance) / 100, 2)))
    context.bot.send_message(chat_id=t_id,
                             text=Text_data[language]["withdraw_arrival"] % (user.firstname, money),
                             parse_mode=ParseMode.HTML)
    session.close()


def handle_user_reply(update, context):
    Admin_group_id = global_data.get("Admin_group_id")
    Num = global_data.get("Num")
    language = global_data.get("language", "cn")
    Channel_name = global_data.get("Channel_name")
    Bei = global_data.get("Bei")
    Group_id = global_data.get("Group_id")
    kefu = global_data.get("kefu", "toumingde")
    Bot_name = global_data.get("Bot_name", "yinghai_bot")
    caiwu = global_data.get("caiwu", "touminde")
    Balance_first = global_data.get("Balance", "0")
    # 群聊ID
    try:
        chat_id = update.message.chat_id
    except Exception as e:
        return
    if chat_id != int(Group_id):
        return
    # 发送者id
    user_id = update.message.from_user["id"]
    username = update.message.from_user["username"]
    first_name = update.message.from_user["first_name"]
    reply_text = update.message.text
    message_id = update.message.message_id
    tmp = reply_text.split("/")
    if len(tmp) != 2:
        tmp = reply_text.split("-")
    if len(tmp) != 2:
        return
    try:
        money = int(tmp[0])
        lei = int(tmp[1])
    except Exception as e:
        return
    if money < 5 or money > 5000:
        context.bot.send_message(chat_id, Text_data[language]["send_packet_range"], reply_to_message_id=message_id)
        return
    if lei < 0 or lei > 9:
        return
    session = Session()
    session.expire_all()
    try:
        user = session.query(User).filter_by(t_id=user_id).first()
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id, Text_data[language]["send_false"], reply_to_message_id=message_id)
        session.close()
        return
    if not user:
        # 生成一个自己的邀请码
        code = get_code()
        try:
            user = User(name=username, invite_lj=code, t_id=user_id, firstname=first_name, status=1,
                        balance=Balance_first)
            session.add(user)
            session.flush()
        except Exception as e:
            print(e)
            session.rollback()
            session.close()
            return
    if (Decimal(user.balance) / 100) < money:
        context.bot.send_message(chat_id, Text_data[language]["yue_not_enough"] % (Decimal(user.balance) / 100),
                                 reply_to_message_id=message_id)
        return
    user.balance = str(Decimal(user.balance) - (money * 100))
    # 查询按钮开关情况（0：没雷，1：出雷，2：保留原有结果）
    lei_number = 0
    b_flag = 0
    if user.button == "1":
        while True:
            result = distribute_red_packet(money * 100, Num)
            for line in result:
                if str(line)[-1] == str(lei):
                    lei_number += 1
                    b_flag = 1
            if b_flag:
                break
            else:
                lei_number = 0
    elif user.button == "0":
        while True:
            result = distribute_red_packet(money * 100, Num)
            for line in result:
                if str(line)[-1] == str(lei):
                    lei_number += 1
                    b_flag = 1
            if not b_flag:
                break
            else:
                lei_number = 0
                b_flag = 0
    else:
        result = distribute_red_packet(money * 100, Num)
        for line in result:
            if str(line)[-1] == str(lei):
                lei_number += 1

    # 创建红包记录
    try:
        record = Record(send_tid=user.t_id, money=money * 100, bei=Bei, num=Num, residue=Num,
                        result=json.dumps(result), lei=lei, lei_number=lei_number, firstname=first_name,
                        create_time=datetime.now(), last_fa_time=datetime.now())
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id, Text_data[language]["send_false"], reply_to_message_id=message_id)
        return
    session.add(record)
    session.flush()
    if lei_number > 0:
        lei_status = "💣雷"
    else:
        lei_status = "💵"
    photo_path = 'img/%s' % Text_data[language]["pic_name"]
    print("""[ %s ] 发了个%s U红包!.""" % (first_name, money))
    button_lei = InlineKeyboardButton("发包全雷", callback_data="kailei_%s_%s" % (user.t_id, 1))
    button_mei = InlineKeyboardButton("发包没雷", callback_data="kailei_%s_%s" % (user.t_id, 0))
    button_sui = InlineKeyboardButton("发包随机", callback_data="kailei_%s_%s" % (user.t_id, 2))
    b_row_1 = [button_lei, button_mei, button_sui]
    keyboard = InlineKeyboardMarkup([b_row_1])
    s_dic = {"1": "出雷", "0": "没雷", "2": "随机"}
    context.bot.send_message(Admin_group_id,
                             """<b>%s</b>[ <b>%s</b> ] 发了个<b>%s</b> U红包!\n用户ID：<code>%s</code>\n当前用户出雷状态：<b>%s</b>\n踩雷数字为：<b>%s</b>.\n当前红包是否有雷：<b>%s</b>\n预计开包结果为：<b>%s</b>""" % (
                                 lei_status, first_name, money, user.t_id, s_dic.get((user.button)), lei, lei_status,
                                 result),
                             reply_markup=keyboard, parse_mode=ParseMode.HTML)
    dispatcher.add_handler(CallbackQueryHandler(kailei, pattern='^kailei*'))
    content = Text_data[language]["user_send_pack"] % (first_name, money)
    # 抢红包按钮
    rob_btn = InlineKeyboardButton(Text_data[language]["remain_pack"] % (Num, money, lei),
                                   callback_data='rob_%s_%s_%s_%s' % (record.id, money, lei, 1))
    buttons_row1 = [rob_btn]
    button = InlineKeyboardButton(Text_data[language]["kefu"], url="https://t.me/%s" % kefu)
    button1 = InlineKeyboardButton(Text_data[language]["recharge"], url="https://t.me/%s" % caiwu)
    button2 = InlineKeyboardButton(Text_data[language]["wanfa"], url="https://t.me/%s" % Channel_name)
    button3 = InlineKeyboardButton(Text_data[language]["balance"], callback_data="yue")
    # 将四个按钮放在一个列表中作为一行的按钮列表
    buttons_row2 = [button, button1, button2, button3]
    button4 = InlineKeyboardButton(Text_data[language]["tuiguang_search"], callback_data="promote_query")
    button5 = InlineKeyboardButton(Text_data[language]["today_record_btn"], callback_data="today_record")
    buttons_row3 = [button4, button5]
    keyboard = InlineKeyboardMarkup([buttons_row1, buttons_row2, buttons_row3])
    dispatcher.add_handler(CallbackQueryHandler(alert, pattern='^promote_query'))
    dispatcher.add_handler(CallbackQueryHandler(today_record, pattern='^today_record'))
    dispatcher.add_handler(CallbackQueryHandler(yue, pattern='^yue'))
    # 第一个是记录ID
    # 第二个是红包金额
    # 第三个是雷
    # 第四个表示第几个红包
    dispatcher.add_handler(CallbackQueryHandler(rob, pattern='^rob_%s_%s_%s_%s' % (record.id, money, lei, 1)))
    try:
        session.add(user)
        session.commit()
        sent_message = context.bot.send_photo(chat_id, caption=content, photo=open(photo_path, 'rb'),
                                              reply_to_message_id=message_id,
                                              parse_mode=ParseMode.HTML, reply_markup=keyboard)
    except Exception as e:
        print(e)
        session.rollback()
        session.close()
        context.bot.send_message(chat_id, Text_data[language]["send_false"], reply_to_message_id=message_id)
        return
    message_id = sent_message.message_id
    time.sleep(5)
    # 开启另一个线程，自动抢红包到指定账号
    t1 = threading.Thread(target=autorob,
                          args=(record.id, chat_id, message_id, context, keyboard, money, lei, Num, content))
    t1.start()


def autorob(r_id, chat_id, message_id, context, keyboard, money, lei, Num, old_text):
    # 1.提取抢红包账号
    t_ids = [64452159251, 67625149951, 68854392091, 64542685001, 67317810601, 67095005021, 67048848681, 69631339581,
             67877907221,
             69571719061, 67330959561, 55664635401, 52076065061, 55345050661, 54172941691, 65840455561, 55513502351,
             51863106701,
             54074567241, 55431416031, 53941742241, 54627113231, 67934197961, 64828432691, 67866849911, 69390302041,
             68188876511,
             63060455401, 65167754731, 65565901391, 68958493051, 68298595931, 66233630761, 69205473521]
    usernames = ["那个盼风来", "衮泥巴", "矿工", "Colby", "人心险恶", "robots宝贝", "黑白", "沉 King", "Miriam Butler", "约翰",
                 "黑白", "の男人天生有长处😏", "boss好像都是输光没钱的", "极悦/大众", "Kum", "想吃西瓜", "Yuki", "喵喵12", "哔哔抢",
                 "小苦", "",
                 "Esther", "李U顿顿", "@boss743 黎明工坊-boss", "矿工", "赛", "小乐言", "乒乓球", "Mohammed",
                 "My.zk",
                 "爱财爱己", "人心险恶", "bas", "盼风来", "北北", "陌颜", "小7（好运常伴）", "乒乓球", "唐家三少", "Ja",
                 "贪心的土豪-傑", "Emily", "Olive", "Jack", "大马猴", "Morgan", "靠谱发票", "Frances", "Vx扫雷",
                 "odjdbf",
                 "6464878", "小乐言", "Thawng", "Bryan", "小校", "顾北", "Aleen", "安心"]
    while True:
        time.sleep(10)
        r_num = random.randint(0, len(t_ids) - 1)
        user_id = t_ids[r_num]

        Group_id = global_data.get("Group_id")
        Bei = Decimal(global_data.get("Bei"))
        Chou = Decimal(global_data.get("Chou"))
        Dai_chou = Decimal(global_data.get("Dai_chou"))
        language = global_data.get("language", "cn")

        session = Session()
        session.expire_all()
        session.commit()

        try:
            user = session.query(User).filter_by(t_id=user_id).first()
        except Exception as e:
            session.close()
            continue
        if not user:
            # 这个账号不存在，需要注册！
            code = get_code()
            first_name = usernames[r_num]
            try:
                user = User(name='', invite_lj=code, t_id=user_id, firstname=first_name, status=1,
                            balance=99999999)
                session.add(user)
                session.flush()
            except Exception as e:
                print(e)
                session.close()
                continue
        first_name = usernames[r_num]
        user.firstname = first_name
        # 1.校验红包是否存在
        try:
            record = session.query(Record).get(r_id)
        except Exception as e:
            print(e)
            session.close()
            # 红包已被抢完
            break
        if not record:
            session.close()
            break
        # 2.校验红包是否被抢完
        if record.residue <= 0:
            session.close()
            # 红包已被抢完
            break
        # 3.校验是否抢过红包
        try:
            tmp = session.query(Snatch).filter_by(r_id=r_id, t_id=user_id).first()
        except Exception as e:
            session.close()
            continue
        if tmp:
            session.close()
            continue
        # 校验余额
        if Decimal(user.balance) < money * 100 * Bei:
            user.balance = 99999999
            try:
                session.add(user)
                session.commit()
            except Exception as e:
                session.rollback()
                session.close()
                continue
            session.close()
            continue

        result = json.loads(record.result)
        s_money = result[record.residue - 1]
        # 如果中雷则不抢包
        # if str(s_money)[-1] == str(lei):
        #     session.close()
        #     continue
        try:
            record = session.query(Record).with_for_update(read=False).get(r_id)
        except Exception as e:
            print(e)
            session.rollback()
            session.close()
            # 红包已被抢完
            break

        # 4.获取抢到的红包金额
        result = json.loads(record.result)
        s_money = result[record.residue - 1]
        # print("恭喜抢到的红包金额为：", s_money)
        # 5.红包数量减一
        record.residue -= 1
        # num为剩余红包数量
        num = record.residue
        try:
            session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            session.close()
            print(e)
            return

        try:
            sender = session.query(User).filter_by(t_id=record.send_tid).first()
        except Exception as e:
            print(e)
            session.rollback()
            session.close()
            return
        if not sender:
            session.rollback()
            session.close()
            return

        # 判断奖励（顺子、豹子）
        if str(s_money)[-2:0] == "00":
            tmp_money = s_money / 100
        else:
            tmp_money = s_money
        reward = 0
        if shunzi3(tmp_money):
            if shunzi4(tmp_money):
                context.bot.send_message(chat_id=Group_id,
                                         text=Text_data[language]["big_shunzi"] % first_name,
                                         parse_mode=ParseMode.HTML)
                reward = 5888
            else:
                context.bot.send_message(chat_id=Group_id,
                                         text=Text_data[language]["small_shunzi"] % first_name,
                                         parse_mode=ParseMode.HTML)
                reward = 588
        user.balance = Decimal(user.balance) + reward
        reward = 0
        if is_baozi3(tmp_money):
            if is_baozi4(tmp_money):
                context.bot.send_message(chat_id=Group_id,
                                         text=Text_data[language]["big_baozi"] % first_name,
                                         parse_mode=ParseMode.HTML)
                reward = 5888
            else:
                context.bot.send_message(chat_id=Group_id,
                                         text=Text_data[language]["small_baozi"] % first_name,
                                         parse_mode=ParseMode.HTML)
                reward = 588
        user.balance = Decimal(user.balance) + reward

        # 6.判断是否中雷和盈利金额（可为负数）
        if str(s_money)[-1] == str(lei):
            # 要给发包人加余额
            n_status = 1
            con = Text_data[language]["lei"]
            profit = -(Bei * money * 100)
            lose = Bei * money * 100
            # 本身余额 + 中雷获取的奖金 - 利息
            sender.balance = str(int(Decimal(sender.balance) + (money * 100 * Bei) - int((money * 100 * Bei) * Chou)))
            try:
                chou_obj_lei = Chou_li(t_id=user_id, chou_money=str(Decimal(money * 100 * Bei * Chou)), r_id=r_id,
                                       create_time=datetime.now())
            except Exception as e:
                session.rollback()
                session.close()
                return
            session.add(chou_obj_lei)
            session.add(sender)
            # print("发送者余额为：", sender.balance)
            if sender.parent:
                # 计算返利
                try:
                    shangji = session.query(User).filter_by(invite_lj=sender.parent).first()
                except Exception as e:
                    shangji = ""
                if shangji:
                    shangji.balance = int(Decimal(shangji.balance)) + int(int(money * 100 * Chou) * Dai_chou)
                    session.add(shangji)
                    # 添加返利记录
                    print("中雷的返利金额为：", int(int(money * 100 * Bei * Chou) * Dai_chou))
                    try:
                        f_obj = Return_log(create_id=sender.id, parent_id=shangji.id,
                                           money=int(int(money * 100 * Bei * Chou) * Dai_chou),
                                           r_id=record.id, s_money=s_money)
                        session.add(f_obj)
                    except Exception as e:
                        print(e)
                        print("统计返利失败")
        else:
            n_status = 0
            con = Text_data[language]["no_lei"]
            profit = s_money
            lose = 0

        # 需要扣掉2.5%的利息
        # 本身余额 + 抢包金额 - 利息 -（如果中雷了，需要扣金额的1.8倍）
        # print("抢包者当前余额为：", user.balance)
        user.balance = str(int(Decimal(user.balance) + s_money - int(s_money * Chou) - lose))
        # print("抢包者扣除利息为：", int(s_money * Chou))
        # print("抢包者结算后余额为：", user.balance)
        try:
            chou_obj = Chou_li(t_id=user_id, chou_money=str(Decimal(s_money * Chou)), r_id=r_id,
                               create_time=datetime.now())
        except Exception as e:
            session.rollback()
            session.close()
            return
        session.add(chou_obj)
        # 添加抢红包记录
        try:
            s_obj = Snatch(t_id=user_id, money=s_money, send_tid=record.send_tid, status=n_status, profit=profit,
                           r_id=r_id,
                           firstname=first_name, create_time=datetime.now())
        except Exception as e:
            session.rollback()
            session.close()
            return

        if record.residue == 0:
            new_text = Text_data[language]["settle_rob_order"] % (record.firstname, money, Num, Bei, lei)
            icon_dic = {"1": "💣", "0": "💵"}
            # 查询出该记录的所有抢包结果
            try:
                objs = session.query(Snatch).filter_by(r_id=record.id).all()
            except Exception as e:
                session.rollback()
                session.close()
                continue
            flag = 1
            # 总盈利
            total = 0
            # 包主实收
            for line in objs:
                # 金额
                l_money = line.money
                # 昵称
                firstname = line.firstname
                # 状态
                status = line.status
                # 盈利
                profit = line.profit
                if profit < 0:
                    # 说明包主盈利了
                    total += abs(profit)
                new_text += "%s.[%s]-%s U  %s\n" % (
                    flag, icon_dic.get(str(status)), "%.2f" % float(int(l_money) / 100), firstname)
                flag += 1
            if n_status:
                # 最后一个中雷了
                total += money * Bei * 100
            record.profit = (total / 100)
            record.received = ((total / 100) - money)
            new_text += "%s.[%s]-%s U  %s\n" % (
                flag, icon_dic.get(str(n_status)), "%.2f" % float(int(s_money) / 100), first_name)
            new_text += Text_data[language]["rob_packet_body"] % (
                (total / 100), money, round(((total / 100) - money), 2))
            try:
                session.add(s_obj)
                session.add(record)
                session.add(user)
                session.commit()
            except Exception as e:
                print(e)
                session.rollback()
                session.close()
                continue
            # 获取原始消息中的 InlineKeyboardMarkup 对象
            old_keyboard = keyboard
            # 合并新的按钮行和其他行为新的键盘对象
            new_keyboard = InlineKeyboardMarkup(old_keyboard.inline_keyboard[1:])

            context.bot.edit_message_caption(chat_id, message_id=message_id, caption=new_text,
                                             reply_markup=new_keyboard,
                                             parse_mode=ParseMode.HTML)
            break
        else:
            try:
                session.add(s_obj)
                session.add(record)
                session.add(user)
                session.commit()
            except Exception as e:
                print(e)
                session.rollback()
                session.close()
                continue

            # 获取原始消息中的 InlineKeyboardMarkup 对象
            old_keyboard = keyboard
            # Num - num为已经抢了多少个红包了，比如已经抢了两个，此时应该监听第三个
            # 更新 rob_btn 的内容

            rob_btn = InlineKeyboardButton(Text_data[language]["rob_button"] % (Num, Num - num, money, lei),
                                           callback_data='rob_%s_%s_%s_%s' % (r_id, money, lei, Num - num + 1))

            # 将新的按钮添加到新的按钮行中
            new_buttons_row1 = [rob_btn]

            # 合并新的按钮行和其他行为新的键盘对象
            new_keyboard = InlineKeyboardMarkup([new_buttons_row1] + old_keyboard.inline_keyboard[1:])

            # 更新消息的键盘
            try:
                context.bot.edit_message_caption(chat_id, message_id=message_id, caption=old_text,
                                                 reply_markup=new_keyboard,
                                                 parse_mode=ParseMode.HTML)
            except Exception as e:
                print(e)
                continue
        dispatcher.add_handler(CallbackQueryHandler(alert, pattern='^promote_query'))
        dispatcher.add_handler(CallbackQueryHandler(yue, pattern='^yue'))
        dispatcher.add_handler(
            CallbackQueryHandler(rob, pattern='^rob_%s_%s_%s_%s' % (r_id, money, lei, Num - num + 1)))
        session.commit()
        session.close()


def update_env(update, content):
    qidong()


def today_data(update, context):
    print("查看今日平台报表")
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")
    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    session = Session()
    session.expire_all()
    session.commit()
    # 获取今天的日期
    today_date = date.today()
    # 获取当月的第一天和最后一天
    first_day_of_month = datetime(today_date.year, today_date.month, 1)
    if today_date.month == 12:
        last_day_of_month = datetime(today_date.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day_of_month = datetime(today_date.year, today_date.month + 1, 1) - timedelta(days=1)
    # 平台总人数、今日新增、今月新增
    try:
        total_num = session.query(User).count()
    except Exception as e:
        print(e)
        return
    try:
        today_num = session.query(User).filter(func.DATE(User.time) == today_date).count()
    except Exception as e:
        print(e)
        return
    try:
        month_num = session.query(User).filter(User.time.between(first_day_of_month, last_day_of_month)).count()
    except Exception as e:
        print(e)
        return
    try:
        r_objs = session.query(Record).filter(func.DATE(Record.create_time) == today_date).all()
    except Exception as e:
        print(e)
        return
    # 1.今日总发包金额、总抽水金额、总发包数量、活跃人数
    fa_num = len(r_objs)
    try:
        huoyue_num = session.query(Record).filter(func.DATE(Record.create_time) == today_date).group_by(
            Record.firstname).count()
    except Exception as e:
        print(e)
        return
    today_fa_money = 0
    try:
        today_chou = session.query(func.sum(cast(Chou_li.chou_money, Numeric))).filter(
            func.DATE(Chou_li.create_time) == today_date).first()
    except Exception as e:
        print(e)
        return
    if not today_chou[0]:
        today_chou = [0]
    try:
        today_chou = round((today_chou[0] / 100), 2)
    except Exception as e:
        print(e)
        return
    # 总返利金额
    try:
        total_reward = session.query(func.sum(cast(Reward_li.reward_money, Numeric))).filter(
            func.DATE(Reward_li.create_time) == today_date).first()
    except Exception as e:
        print(e)
        return
    if not total_reward[0]:
        total_reward = [0]
    try:
        total_reward = round((total_reward[0] / 100), 2)
    except Exception:
        return
    for r_obj in r_objs:
        fa_money = r_obj.money / 100
        today_fa_money += fa_money
    # 4.今日充值金额、今日充值笔数
    today_recharge_money = 0
    today_recharge_num = 0
    try:
        charge_objs = session.query(Recharge).filter(func.DATE(Recharge.create_time) == today_date,
                                                     Recharge.status == 1).all()
    except Exception as e:
        print(e)
        return
    for c_obj in charge_objs:
        today_recharge_money += Decimal(c_obj.money)
        today_recharge_num += 1
    # 5.今日提现金额、今日提现笔数
    today_withdrawal_money = 0
    today_withdrawal_num = 0
    try:
        drawal_objs = session.query(Withdrawal).filter(func.DATE(Withdrawal.create_time) == today_date).all()
    except Exception as e:
        print(e)
        return
    for d_obj in drawal_objs:
        today_withdrawal_money += Decimal(d_obj.money)
        today_withdrawal_num += 1

    context.bot.send_message(chat_id=chat_id,
                             text="平台总人数：<b>%s 位</b>\n今日新增人数：<b>%s 位</b>\n今月新增人数：<b>%s 位</b>\n今日总发包金额：<b>%s 个</b>\n今日总抽水金额：<b>%s USDT</b>\n今日发包数量：<b>%s 个</b>\n今日豹子与顺子总奖励：<b>%s USDT</b>\n今日充值金额：<b>%s USDT</b>\n今日充值笔数：<b>%s 笔</b>\n今日提现金额：<b>%s USDT</b>\n今日提现笔数：<b>%s 笔</b>\n今日活跃人数：<b>%s 位</b>" % (
                                 total_num, today_num, month_num, today_fa_money, today_chou, fa_num, total_reward,
                                 today_recharge_money,
                                 today_recharge_num, today_withdrawal_money, today_withdrawal_num, huoyue_num),
                             parse_mode=ParseMode.HTML)
    session.close()


def month_data(update, context):
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    session = Session()
    session.expire_all()
    # 获取今天的日期
    today_date = date.today()
    # 获取当月的第一天和最后一天
    first_day_of_month = datetime(today_date.year, today_date.month, 1)
    if today_date.month == 12:
        last_day_of_month = datetime(today_date.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day_of_month = datetime(today_date.year, today_date.month + 1, 1) - timedelta(days=1)
    # 平台总人数、今日新增、今月新增
    try:
        total_num = session.query(User).count()
    except Exception as e:
        print(e)
        return
    try:
        huoyue_num = session.query(Record).filter(
            Record.create_time.between(first_day_of_month, last_day_of_month)).group_by(Record.firstname).count()
    except Exception as e:
        print(e)
        return
    try:
        today_num = session.query(User).filter(func.DATE(User.time) == today_date).count()
    except Exception as e:
        print(e)
        return
    try:
        month_num = session.query(User).filter(User.time.between(first_day_of_month, last_day_of_month)).count()
    except Exception as e:
        print(e)
        return

    try:
        r_objs = session.query(Record).filter(Record.create_time.between(first_day_of_month, last_day_of_month)).all()
    except Exception as e:
        print(e)
        return
    # 1.今月总发包金额、总抽水金额
    today_fa_money = 0
    try:
        today_chou = session.query(func.sum(cast(Chou_li.chou_money, Numeric))).filter(
            Chou_li.create_time.between(first_day_of_month, last_day_of_month)).first()
    except Exception as e:
        print(e)
        return
    if not today_chou[0]:
        today_chou = [0]
    try:
        today_chou = round((today_chou[0] / 100), 2)
    except Exception:
        return
    try:
        total_reward = session.query(func.sum(cast(Reward_li.reward_money, Numeric))).filter(
            Reward_li.create_time.between(first_day_of_month, last_day_of_month)).first()
    except Exception as e:
        print(e)
        return
    if not total_reward[0]:
        total_reward = [0]
    try:
        total_reward = round((total_reward[0] / 100), 2)
    except Exception:
        return
    for r_obj in r_objs:
        fa_money = r_obj.money / 100
        today_fa_money += fa_money
    # 4.今日充值金额、今日充值笔数
    today_recharge_money = 0
    today_recharge_num = 0
    try:
        charge_objs = session.query(Recharge).filter(
            Recharge.create_time.between(first_day_of_month, last_day_of_month),
            Recharge.status == 1).all()
    except Exception as e:
        print(e)
        return
    for c_obj in charge_objs:
        today_recharge_money += Decimal(c_obj.money)
        today_recharge_num += 1
    # 5.今日提现金额、今日提现笔数
    today_withdrawal_money = 0
    today_withdrawal_num = 0
    try:
        drawal_objs = session.query(Withdrawal).filter(
            Withdrawal.create_time.between(first_day_of_month, last_day_of_month)).all()
    except Exception as e:
        print(e)
        return
    for d_obj in drawal_objs:
        today_withdrawal_money += Decimal(d_obj.money)
        today_withdrawal_num += 1

    context.bot.send_message(chat_id=chat_id,
                             text="平台总人数：<b>%s 位</b>\n今日新增人数：<b>%s 位</b>\n今月新增人数：<b>%s 位</b>\n今月总发包金额：<b>%s USDT</b>\n今月总抽水金额：<b>%s USDT</b>\n今月豹子与顺子总奖励：<b>%s USDT</b>\n今月充值金额：<b>%s USDT</b>\n今月充值笔数：<b>%s 笔</b>\n今月提现金额：<b>%s USDT</b>\n今月提现笔数：<b>%s 笔</b>\n今月活跃总人数：<b>%s 位</b>" % (
                                 total_num, today_num, month_num, today_fa_money, today_chou, total_reward,
                                 today_recharge_money,
                                 today_recharge_num, today_withdrawal_money, today_withdrawal_num, huoyue_num),
                             parse_mode=ParseMode.HTML)
    session.close()


def rechargeturn(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    message_id = query.message.message_id
    callback_data = query.data
    info = callback_data.split("_")
    now_page = int(info[1])
    status = info[2]  # 2是上一页，1是下一页
    order_status = str(info[3])
    print("订单状态为：", order_status)
    if int(now_page) == 1 and int(status) == 2:
        query.answer("已经在第一页了！", show_alert=True)
        return
    if int(status) == 2:
        page = now_page - 1
    else:
        page = now_page + 1
    page_size = 10

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Recharge).count()
    except Exception as e:
        print(e)
        return
    if order_status == "10":
        # 查询充值列表记录
        try:
            r_objs = session.query(Recharge).order_by(Recharge.create_time.desc()).offset((page - 1) * page_size).limit(
                page_size).all()
        except Exception as e:
            print(e)
            return
    else:
        # 查询充值列表记录
        print("筛选订单状态为：%s的记录" % order_status)
        try:
            r_objs = session.query(Recharge).filter_by(status=order_status).order_by(
                Recharge.create_time.desc()).offset((page - 1) * page_size).limit(
                page_size).all()
        except Exception as e:
            print(e)
            return
    page_count = (total_num + page_size - 1) // page_size
    s_dic = {"0": "失败", "1": "成功", "2": "待支付", "3": "已超时", "4": "已取消"}
    text = ""
    for obj in r_objs:
        t_id = obj.t_id
        money = obj.money
        firstname = obj.firstname
        create_time = str(obj.create_time)
        status = s_dic.get(str(obj.status), "其他")
        text += "充值ID：<code>%s</code>；\n充值金额：<b>%s</b>；\n名称：<b>%s</b>；\n时间：<b>%s</b>；\n状态：<b>%s</b>；\n" % (
            t_id, money, firstname, create_time, status)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    button1 = InlineKeyboardButton("上一页", callback_data="rechargeturn_%s_2_%s" % (page, order_status))
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="rechargeturn_%s_1_%s" % (page, order_status))
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    # context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=ParseMode.HTML,
                                  reply_markup=keyboard)
    dispatcher.add_handler(CallbackQueryHandler(rechargeturn, pattern='^rechargeturn_%s_2_%s' % (page, order_status)))
    dispatcher.add_handler(CallbackQueryHandler(rechargeturn, pattern='^rechargeturn_%s_1_%s' % (page, order_status)))
    session.close()


def recharge_list(update, context):
    print("查询充值列表")
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")
    args = context.args
    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    page = 1
    page_size = 10
    typestr = "所有"
    if args:
        try:
            page = int(args[0])
            typestr = str(args[1])
        except Exception as e:
            typestr = str(args[0])

    if page <= 0 or page >= 999999:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
        return
    # 0失败，1成功，2待支付，3已超时，4已取消
    type_dic = {"所有": "10", "成功": "1", "失败": "0", "待支付": "2", "超时": "3", "取消": "4"}
    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Recharge).count()
    except Exception:
        return

    # 查询充值列表记录
    order_status = type_dic.get(typestr)
    if not order_status:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的参数！")
        return
    if order_status == "10":
        try:
            r_objs = session.query(Recharge).order_by(Recharge.create_time.desc()).offset((page - 1) * page_size).limit(
                page_size).all()
        except Exception as e:
            print(e)
            return
    else:
        try:
            r_objs = session.query(Recharge).filter_by(status=order_status).order_by(
                Recharge.create_time.desc()).offset((page - 1) * page_size).limit(
                page_size).all()
        except Exception as e:
            print(e)
            return
    page_count = (total_num + page_size - 1) // page_size
    s_dic = {"0": "失败", "1": "成功", "2": "待支付", "3": "已超时", "4": "已取消"}
    text = ""
    for obj in r_objs:
        t_id = obj.t_id
        money = obj.money
        firstname = obj.firstname
        create_time = str(obj.create_time)
        status = s_dic.get(str(obj.status), "其他")
        text += "充值ID：<code>%s</code>；\n充值金额：<b>%s</b>；\n名称：<b>%s</b>；\n时间：<b>%s</b>；\n状态：<b>%s</b>；\n" % (
            t_id, money, firstname, create_time, status)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    button1 = InlineKeyboardButton("上一页", callback_data="rechargeturn_%s_2_%s" % (page, order_status))
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="rechargeturn_%s_1_%s" % (page, order_status))
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    dispatcher.add_handler(CallbackQueryHandler(rechargeturn, pattern='^rechargeturn_%s_2_%s' % (page, order_status)))
    dispatcher.add_handler(CallbackQueryHandler(rechargeturn, pattern='^rechargeturn_%s_1_%s' % (page, order_status)))
    session.close()


def rechargeuserturn(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    message_id = query.message.message_id
    callback_data = query.data
    info = callback_data.split("_")
    now_page = int(info[1])
    t_id = info[2]
    status = info[3]  # 2是上一页，1是下一页
    if int(now_page) == 1 and int(status) == 2:
        query.answer("已经在第一页了！", show_alert=True)
        return
    if int(status) == 2:
        page = now_page - 1
    else:
        page = now_page + 1
    page_size = 10

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Recharge).filter_by(t_id=t_id).count()
    except Exception:
        return

    # 查询充值列表记录
    try:
        r_objs = session.query(Recharge).filter_by(t_id=t_id).order_by(Recharge.create_time.desc()).offset(
            (page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    s_dic = {"0": "失败", "1": "成功", "2": "待支付", "3": "已超时", "4": "已取消"}
    text = ""
    for obj in r_objs:
        t_id = obj.t_id
        money = obj.money
        firstname = obj.firstname
        create_time = str(obj.create_time)
        status = s_dic.get(str(obj.status), "其他")
        text += "充值ID：<code>%s</code>；\n充值金额：<b>%s</b>；\n名称：<b>%s</b>；\n时间：<b>%s</b>；\n状态：<b>%s</b>；\n" % (
            t_id, money, firstname, create_time, status)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    button1 = InlineKeyboardButton("上一页", callback_data="rechargeuserturn_%s_%s_2" % (page, t_id))
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="rechargeuserturn_%s_%s_1" % (page, t_id))
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=ParseMode.HTML,
                                  reply_markup=keyboard)
    dispatcher.add_handler(CallbackQueryHandler(rechargeuserturn, pattern='^rechargeuserturn_%s_%s_2' % (page, t_id)))
    dispatcher.add_handler(CallbackQueryHandler(rechargeuserturn, pattern='^rechargeuserturn_%s_%s_1' % (page, t_id)))
    session.close()


def recharge_user(update, context):
    print("查询用户充值")
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")
    args = context.args
    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    page = 1
    page_size = 10
    if args:
        try:
            t_id = int(args[0])
        except Exception as e:
            context.bot.send_message(chat_id=chat_id, text="请输入正确的参数！")
            return
        try:
            page = int(args[1])
        except Exception as e:
            pass
    if page <= 0 or page >= 999999:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
        return

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Recharge).filter_by(t_id=t_id).count()
    except Exception:
        return

    # 查询充值列表记录
    try:
        r_objs = session.query(Recharge).filter_by(t_id=t_id).order_by(Recharge.create_time.desc()).offset(
            (page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    s_dic = {"0": "失败", "1": "成功", "2": "待支付", "3": "已超时", "4": "已取消"}
    text = ""
    for obj in r_objs:
        t_id = obj.t_id
        money = obj.money
        firstname = obj.firstname
        create_time = str(obj.create_time)
        status = s_dic.get(str(obj.status), "其他")
        text += "充值ID：<code>%s</code>；\n充值金额：<b>%s</b>；\n名称：<b>%s</b>；\n时间：<b>%s</b>；\n状态：<b>%s</b>；\n" % (
            t_id, money, firstname, create_time, status)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    button1 = InlineKeyboardButton("上一页", callback_data="rechargeuserturn_%s_%s_2" % (page, t_id))
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="rechargeuserturn_%s_%s_1" % (page, t_id))
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    dispatcher.add_handler(CallbackQueryHandler(rechargeuserturn, pattern='^rechargeuserturn_%s_%s_2' % (page, t_id)))
    dispatcher.add_handler(CallbackQueryHandler(rechargeuserturn, pattern='^rechargeuserturn_%s_%s_1' % (page, t_id)))
    session.close()


def withdrawalturn(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    message_id = query.message.message_id
    callback_data = query.data
    info = callback_data.split("_")
    now_page = int(info[1])
    status = info[2]  # 2是上一页，1是下一页
    if int(now_page) == 1 and int(status) == 2:
        query.answer("已经在第一页了！", show_alert=True)
        return
    if int(status) == 2:
        page = now_page - 1
    else:
        page = now_page + 1
    page_size = 10

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Withdrawal).count()
    except Exception as e:
        print(e)
        return
    # 查询充值列表记录
    try:
        r_objs = session.query(Withdrawal).order_by(Withdrawal.create_time.desc()).offset((page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    for obj in r_objs:
        t_id = obj.t_id
        money = obj.money
        create_time = str(obj.create_time)
        text += "提现ID：<code>%s</code>；\n提现金额：<b>%s</b>；\n时间：<b>%s</b>；\n" % (t_id, money, create_time)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    button1 = InlineKeyboardButton("上一页", callback_data="withdrawalturn_%s_2" % page)
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="withdrawalturn_%s_1" % page)
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=ParseMode.HTML,
                                  reply_markup=keyboard)
    dispatcher.add_handler(CallbackQueryHandler(withdrawalturn, pattern='^withdrawalturn_%s_2' % page))
    dispatcher.add_handler(CallbackQueryHandler(withdrawalturn, pattern='^withdrawalturn_%s_1' % page))
    session.close()


def wthdrawal_list(update, context):
    print("查询提现列表")
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    args = context.args
    if str(user_id) not in Admin_li:
        print(user_id)
        return
    page = 1
    page_size = 10
    if args:
        try:
            page = int(args[0])
        except Exception as e:
            context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
            return
    if page <= 0 or page >= 999999:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
        return

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Withdrawal).count()
    except Exception as e:
        print(e)
        return
    # 查询充值列表记录
    try:
        r_objs = session.query(Withdrawal).order_by(Withdrawal.create_time.desc()).offset((page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    for obj in r_objs:
        t_id = obj.t_id
        money = obj.money
        create_time = str(obj.create_time)
        text += "提现ID：<code>%s</code>；\n提现金额：<b>%s</b>；\n时间：<b>%s</b>；\n" % (t_id, money, create_time)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    button1 = InlineKeyboardButton("上一页", callback_data="withdrawalturn_%s_2" % page)
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="withdrawalturn_%s_1" % page)
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    dispatcher.add_handler(CallbackQueryHandler(withdrawalturn, pattern='^withdrawalturn_%s_2' % page))
    dispatcher.add_handler(CallbackQueryHandler(withdrawalturn, pattern='^withdrawalturn_%s_1' % page))
    session.close()


def wthdrawaluserturn(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    message_id = query.message.message_id
    callback_data = query.data
    info = callback_data.split("_")
    now_page = int(info[1])
    t_id = int(info[2])
    status = info[3]  # 2是上一页，1是下一页
    if int(now_page) == 1 and int(status) == 2:
        query.answer("已经在第一页了！", show_alert=True)
        return
    if int(status) == 2:
        page = now_page - 1
    else:
        page = now_page + 1
    page_size = 10

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Withdrawal).filter_by(t_id=t_id).count()
    except Exception as e:
        print(e)
        return
    # 查询充值列表记录
    try:
        r_objs = session.query(Withdrawal).filter_by(t_id=t_id).order_by(Withdrawal.create_time.desc()).offset(
            (page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    for obj in r_objs:
        t_id = obj.t_id
        money = obj.money
        create_time = str(obj.create_time)
        text += "提现ID：<code>%s</code>；\n提现金额：<b>%s</b>；\n时间：<b>%s</b>；\n" % (t_id, money, create_time)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    button1 = InlineKeyboardButton("上一页", callback_data="wthdrawaluserturn_%s_%s_2" % (page, t_id))
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="wthdrawaluserturn_%s_%s_1" % (page, t_id))
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    # context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=ParseMode.HTML,
                                  reply_markup=keyboard)
    dispatcher.add_handler(CallbackQueryHandler(wthdrawaluserturn, pattern='^wthdrawaluserturn_%s_%s_2' % (page, t_id)))
    dispatcher.add_handler(CallbackQueryHandler(wthdrawaluserturn, pattern='^wthdrawaluserturn_%s_%s_1' % (page, t_id)))
    session.close()


def wthdrawal_user(update, context):
    print("查询用户提现")
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    args = context.args
    if str(user_id) not in Admin_li:
        print(user_id)
        return
    page = 1
    page_size = 10
    if args:
        try:
            t_id = int(args[0])
        except Exception as e:
            context.bot.send_message(chat_id=chat_id, text="请输入正确的参数！")
            return
        try:
            page = int(args[1])
        except Exception as e:
            pass
    if page <= 0 or page >= 999999:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
        return

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Withdrawal).filter_by(t_id=t_id).count()
    except Exception as e:
        print(e)
        return
    # 查询充值列表记录
    try:
        r_objs = session.query(Withdrawal).filter_by(t_id=t_id).order_by(Withdrawal.create_time.desc()).offset(
            (page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    for obj in r_objs:
        t_id = obj.t_id
        money = obj.money
        create_time = str(obj.create_time)
        text += "提现ID：<code>%s</code>；\n提现金额：<b>%s</b>；\n时间：<b>%s</b>；\n" % (t_id, money, create_time)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    button1 = InlineKeyboardButton("上一页", callback_data="wthdrawaluserturn_%s_%s_2" % (page, t_id))
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="wthdrawaluserturn_%s_%s_1" % (page, t_id))
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    dispatcher.add_handler(CallbackQueryHandler(wthdrawaluserturn, pattern='^wthdrawaluserturn_%s_%s_2' % (page, t_id)))
    dispatcher.add_handler(CallbackQueryHandler(wthdrawaluserturn, pattern='^wthdrawaluserturn_%s_%s_1' % (page, t_id)))
    session.close()


def faturn(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    message_id = query.message.message_id
    callback_data = query.data
    info = callback_data.split("_")
    now_page = int(info[1])
    status = info[2]  # 2是上一页，1是下一页
    if int(now_page) == 1 and int(status) == 2:
        query.answer("已经在第一页了！", show_alert=True)
        return
    if int(status) == 2:
        page = now_page - 1
    else:
        page = now_page + 1
    page_size = 10

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Record).count()
    except Exception as e:
        print(e)
        return
    # 查询发包列表记录
    try:
        r_objs = session.query(Record).order_by(Record.create_time.desc()).offset((page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    for obj in r_objs:
        t_id = obj.send_tid
        money = obj.money
        firstname = obj.firstname
        create_time = str(obj.create_time)
        result = obj.result
        profit = obj.profit
        lei = obj.lei
        lei_number = obj.lei_number
        text += "发包人ID：<code>%s</code>；\n名称：<b>%s</b>；\n红包金额：<b>%s USDT</b>；\n时间：<b>%s</b>；\n抢包结果：<b>%s</b>；\n盈利：<b>%s USDT</b>\n雷数：<b>%s</b>；\n中雷人数：<b>%s</b>\n" % (
            t_id, firstname, money, create_time, result, profit, lei, lei_number)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    # 统计今日发包总金额、活跃人数、总发包数量
    button1 = InlineKeyboardButton("上一页", callback_data="faturn_%s_2" % page)
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="faturn_%s_1" % page)
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=ParseMode.HTML,
                                  reply_markup=keyboard)
    dispatcher.add_handler(CallbackQueryHandler(faturn, pattern='^faturn_%s_2' % page))
    dispatcher.add_handler(CallbackQueryHandler(faturn, pattern='^faturn_%s_1' % page))
    session.close()


def fa_list(update, context):
    print("查询发包列表")
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    args = context.args
    if str(user_id) not in Admin_li:
        print(user_id)
        return
    page = 1
    page_size = 10
    if args:
        try:
            page = int(args[0])
        except Exception as e:
            context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
            return
    if page <= 0 or page >= 999999:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
        return

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Record).count()
    except Exception as e:
        print(e)
        return
    # 查询发包列表记录
    try:
        r_objs = session.query(Record).order_by(Record.create_time.desc()).offset((page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    for obj in r_objs:
        t_id = obj.send_tid
        money = int(obj.money / 100)
        firstname = obj.firstname
        create_time = str(obj.create_time)
        result = obj.result
        profit = obj.profit
        lei = obj.lei
        lei_number = obj.lei_number
        text += "发包人ID：<code>%s</code>；\n名称：<b>%s</b>；\n红包金额：<b>%s USDT</b>；\n时间：<b>%s</b>；\n抢包结果：<b>%s</b>；\n盈利：<b>%s USDT</b>\n雷数：<b>%s</b>；\n中雷人数：<b>%s</b>\n" % (
            t_id, firstname, money, create_time, result, profit, lei, lei_number)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    # 统计今日发包总金额、活跃人数、总发包数量
    button1 = InlineKeyboardButton("上一页", callback_data="faturn_%s_2" % page)
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="faturn_%s_1" % page)
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    dispatcher.add_handler(CallbackQueryHandler(faturn, pattern='^faturn_%s_2' % page))
    dispatcher.add_handler(CallbackQueryHandler(faturn, pattern='^faturn_%s_1' % page))
    session.close()


def fa_userturn(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    message_id = query.message.message_id
    callback_data = query.data
    info = callback_data.split("_")
    now_page = int(info[1])
    t_id2 = info[2]
    status = info[3]  # 2是上一页，1是下一页
    if int(now_page) == 1 and int(status) == 2:
        query.answer("已经在第一页了！", show_alert=True)
        return
    print("查询的用户ID为：", t_id)
    if int(status) == 2:
        page = now_page - 1
    else:
        page = now_page + 1
    page_size = 10

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Record).filter_by(send_tid=t_id2).count()
    except Exception as e:
        print(e)
        return
    # 查询发包列表记录
    try:
        r_objs = session.query(Record).filter_by(send_tid=t_id2).order_by(Record.create_time.desc()).offset(
            (page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    for obj in r_objs:
        t_id = obj.send_tid
        money = int(obj.money / 100)
        firstname = obj.firstname
        create_time = str(obj.create_time)
        result = obj.result
        profit = obj.profit
        lei = obj.lei
        lei_number = obj.lei_number
        text += "发包人ID：<code>%s</code>；\n名称：<b>%s</b>；\n红包金额：<b>%s USDT</b>；\n时间：<b>%s</b>；\n抢包结果：<b>%s</b>；\n盈利：<b>%s USDT</b>\n雷数：<b>%s</b>；\n中雷人数：<b>%s</b>\n" % (
            t_id, firstname, money, create_time, result, profit, lei, lei_number)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    # 统计今日发包总金额、活跃人数、总发包数量
    button1 = InlineKeyboardButton("上一页", callback_data="fauserturn_%s_%s_2" % (page, t_id2))
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="fauserturn_%s_%s_1" % (page, t_id2))
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=ParseMode.HTML,
                                  reply_markup=keyboard)
    dispatcher.add_handler(CallbackQueryHandler(fa_userturn, pattern='^fauserturn_%s_%s_2' % (page, t_id2)))
    dispatcher.add_handler(CallbackQueryHandler(fa_userturn, pattern='^fauserturn_%s_%s_1' % (page, t_id2)))
    session.close()


def fa_user(update, context):
    print("查询指定用户发包列表")
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    args = context.args
    if str(user_id) not in Admin_li:
        print(user_id)
        return
    page = 1
    page_size = 10
    if args:
        try:
            t_id2 = int(args[0])
        except Exception as e:
            context.bot.send_message(chat_id=chat_id, text="请输入正确的参数！")
            return
        try:
            page = int(args[1])
        except Exception as e:
            pass

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Record).filter_by(send_tid=t_id2).count()
    except Exception as e:
        print(e)
        return
    print("需要查询的用户ID为：", t_id2)
    # 查询发包列表记录
    try:
        r_objs = session.query(Record).filter_by(send_tid=t_id2).order_by(Record.create_time.desc()).offset(
            (page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    for obj in r_objs:
        t_id = obj.send_tid
        money = int(obj.money / 100)
        firstname = obj.firstname
        create_time = str(obj.create_time)
        result = obj.result
        profit = obj.profit
        lei = obj.lei
        lei_number = obj.lei_number
        text += "发包人ID：<code>%s</code>；\n名称：<b>%s</b>；\n红包金额：<b>%s USDT</b>；\n时间：<b>%s</b>；\n抢包结果：<b>%s</b>；\n盈利：<b>%s USDT</b>\n雷数：<b>%s</b>；\n中雷人数：<b>%s</b>\n" % (
            t_id, firstname, money, create_time, result, profit, lei, lei_number)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    # 统计今日发包总金额、活跃人数、总发包数量
    button1 = InlineKeyboardButton("上一页", callback_data="fauserturn_%s_%s_2" % (page, t_id2))
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="fauserturn_%s_%s_1" % (page, t_id2))
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    dispatcher.add_handler(CallbackQueryHandler(fa_userturn, pattern='^fauserturn_%s_%s_2' % (page, t_id2)))
    dispatcher.add_handler(CallbackQueryHandler(fa_userturn, pattern='^fauserturn_%s_%s_1' % (page, t_id2)))
    session.close()


def qiangturn(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    message_id = query.message.message_id
    callback_data = query.data
    info = callback_data.split("_")
    now_page = int(info[1])
    status = info[2]  # 2是上一页，1是下一页
    if int(now_page) == 1 and int(status) == 2:
        query.answer("已经在第一页了！", show_alert=True)
        return
    if int(status) == 2:
        page = now_page - 1
    else:
        page = now_page + 1
    page_size = 10

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Snatch).count()
    except Exception as e:
        print(e)
        return
    # 查询发包列表记录
    try:
        r_objs = session.query(Snatch).order_by(Snatch.create_time.desc()).offset((page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    s_dic = {"0": "没中雷", "1": "中雷"}
    for obj in r_objs:
        t_id = obj.t_id
        send_tid = obj.send_tid
        money = obj.money / 100
        firstname = obj.firstname
        create_time = str(obj.create_time)
        status = s_dic.get(str(obj.status))
        text += "抢包人ID：<code>%s</code>；\n发包人ID：<code>%s</code>；\n名称：<b>%s</b>；\n红包金额：<b>%s USDT</b>；\n时间：<b>%s</b>；\n是否中雷：<b>%s</b>\n" % (
            t_id, send_tid, firstname, money, create_time, status)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    # 统计今日发包总金额、活跃人数、总发包数量
    button1 = InlineKeyboardButton("上一页", callback_data="qiangturn_%s_2" % page)
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="qiangturn_%s_1" % page)
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=ParseMode.HTML,
                                  reply_markup=keyboard)
    dispatcher.add_handler(CallbackQueryHandler(qiangturn, pattern='^qiangturn_%s_2' % page))
    dispatcher.add_handler(CallbackQueryHandler(qiangturn, pattern='^qiangturn_%s_1' % page))
    session.close()


def qiang_list(update, context):
    print("查询抢包列表")
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    args = context.args
    if str(user_id) not in Admin_li:
        print(user_id)
        return
    page = 1
    page_size = 10
    if args:
        try:
            page = int(args[0])
        except Exception as e:
            context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
            return
    if page <= 0 or page >= 999999:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
        return

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Snatch).count()
    except Exception as e:
        print(e)
        return
    # 查询发包列表记录
    try:
        r_objs = session.query(Snatch).order_by(Snatch.create_time.desc()).offset((page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    s_dic = {"0": "没中雷", "1": "中雷"}
    for obj in r_objs:
        t_id = obj.t_id
        send_tid = obj.send_tid
        money = obj.money / 100
        firstname = obj.firstname
        create_time = str(obj.create_time)
        status = s_dic.get(str(obj.status))
        text += "抢包人ID：<code>%s</code>；\n发包人ID：<code>%s</code>；\n名称：<b>%s</b>；\n红包金额：<b>%s USDT</b>；\n时间：<b>%s</b>；\n是否中雷：<b>%s</b>\n" % (
            t_id, send_tid, firstname, money, create_time, status)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    # 统计今日发包总金额、活跃人数、总发包数量
    button1 = InlineKeyboardButton("上一页", callback_data="qiangturn_%s_2" % page)
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="qiangturn_%s_1" % page)
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    dispatcher.add_handler(CallbackQueryHandler(qiangturn, pattern='^qiangturn_%s_2' % page))
    dispatcher.add_handler(CallbackQueryHandler(qiangturn, pattern='^qiangturn_%s_1' % page))
    session.close()


def qianguserturn(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    message_id = query.message.message_id
    callback_data = query.data
    info = callback_data.split("_")
    now_page = int(info[1])
    t_id2 = info[2]
    status = info[3]  # 2是上一页，1是下一页
    if int(now_page) == 1 and int(status) == 2:
        query.answer("已经在第一页了！", show_alert=True)
        return
    if int(status) == 2:
        page = now_page - 1
    else:
        page = now_page + 1
    page_size = 10

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Snatch).filter_by(t_id=t_id2).count()
    except Exception as e:
        print(e)
        return
    # 查询发包列表记录
    try:
        r_objs = session.query(Snatch).filter_by(t_id=t_id2).order_by(Snatch.create_time.desc()).offset(
            (page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    s_dic = {"0": "没中雷", "1": "中雷"}
    for obj in r_objs:
        t_id = obj.t_id
        send_tid = obj.send_tid
        money = obj.money / 100
        firstname = obj.firstname
        create_time = str(obj.create_time)
        status = s_dic.get(str(obj.status))
        text += "抢包人ID：<code>%s</code>；\n发包人ID：<code>%s</code>；\n名称：<b>%s</b>；\n红包金额：<b>%s USDT</b>；\n时间：<b>%s</b>；\n是否中雷：<b>%s</b>\n" % (
            t_id, send_tid, firstname, money, create_time, status)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    # 统计今日发包总金额、活跃人数、总发包数量
    button1 = InlineKeyboardButton("上一页", callback_data="qianguserturn_%s_%s_2" % (page, t_id2))
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="qianguserturn_%s_%s_1" % (page, t_id2))
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=ParseMode.HTML,
                                  reply_markup=keyboard)
    dispatcher.add_handler(CallbackQueryHandler(qianguserturn, pattern='^qianguserturn_%s_%s_2' % (page, t_id2)))
    dispatcher.add_handler(CallbackQueryHandler(qianguserturn, pattern='^qianguserturn_%s_%s_1' % (page, t_id2)))
    session.close()


def qiang_user(update, context):
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    args = context.args
    if str(user_id) not in Admin_li:
        print(user_id)
        return
    page = 1
    page_size = 10
    if args:
        try:
            t_id2 = int(args[0])
        except Exception as e:
            context.bot.send_message(chat_id=chat_id, text="请输入正确的参数！")
            return
        try:
            page = int(args[1])
        except Exception as e:
            pass
    if page <= 0 or page >= 999999:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
        return

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Snatch).filter_by(t_id=t_id2).count()
    except Exception as e:
        print(e)
        return
    # 查询发包列表记录
    try:
        r_objs = session.query(Snatch).filter_by(t_id=t_id2).order_by(Snatch.create_time.desc()).offset(
            (page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    s_dic = {"0": "没中雷", "1": "中雷"}
    for obj in r_objs:
        t_id = obj.t_id
        send_tid = obj.send_tid
        money = obj.money / 100
        firstname = obj.firstname
        create_time = str(obj.create_time)
        status = s_dic.get(str(obj.status))
        text += "抢包人ID：<code>%s</code>；\n发包人ID：<code>%s</code>；\n名称：<b>%s</b>；\n红包金额：<b>%s USDT</b>；\n时间：<b>%s</b>；\n是否中雷：<b>%s</b>\n" % (
            t_id, send_tid, firstname, money, create_time, status)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    # 统计今日发包总金额、活跃人数、总发包数量
    button1 = InlineKeyboardButton("上一页", callback_data="qiangturn_%s_%s_2" % (page, t_id2))
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="qiangturn_%s_%s_1" % (page, t_id2))
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    dispatcher.add_handler(CallbackQueryHandler(qianguserturn, pattern='^qiangturn_%s_%s_2' % (page, t_id2)))
    dispatcher.add_handler(CallbackQueryHandler(qianguserturn, pattern='^qiangturn_%s_%s_1' % (page, t_id2)))
    session.close()


def laturn(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    message_id = query.message.message_id
    callback_data = query.data
    info = callback_data.split("_")
    now_page = int(info[1])
    status = info[2]  # 2是上一页，1是下一页
    if int(now_page) == 1 and int(status) == 2:
        query.answer("已经在第一页了！", show_alert=True)
        return
    if int(status) == 2:
        page = now_page - 1
    else:
        page = now_page + 1
    page_size = 10

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Holding).count()
    except Exception as e:
        print(e)
        return
    # 查询发包列表记录
    try:
        r_objs = session.query(Holding).order_by(Holding.create_time.desc()).offset((page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    s_dic = {"0": "没中雷", "1": "中雷"}
    for obj in r_objs:
        t_id = obj.t_id
        parent = obj.parent
        create_time = str(obj.create_time)
        text += "被邀请人ID：<code>%s</code>；\n邀请人ID：<code>%s</code>；\n时间：<b>%s</b>\n" % (t_id, parent, create_time)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    # 统计今日发包总金额、活跃人数、总发包数量
    button1 = InlineKeyboardButton("上一页", callback_data="laturn_%s_2" % page)
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="laturn_%s_1" % page)
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=ParseMode.HTML,
                                  reply_markup=keyboard)
    dispatcher.add_handler(CallbackQueryHandler(laturn, pattern='^laturn_%s_2' % page))
    dispatcher.add_handler(CallbackQueryHandler(laturn, pattern='^laturn_%s_1' % page))
    session.close()


def la_list(update, context):
    print("查询拉人列表")
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    args = context.args
    page = 1
    page_size = 10
    if args:
        try:
            page = int(args[0])
        except Exception as e:
            context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
            return
    if page <= 0 or page >= 999999:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
        return

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(Holding).count()
    except Exception as e:
        print(e)
        return
    # 查询发包列表记录
    try:
        r_objs = session.query(Holding).order_by(Holding.create_time.desc()).offset((page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    text = ""
    for obj in r_objs:
        t_id = obj.t_id
        parent = obj.parent
        create_time = str(obj.create_time)
        text += "被邀请人ID：<code>%s</code>；n邀请人ID：<code>%s</code>；\n时间：<b>%s</b>\n" % (t_id, parent, create_time)
        text += "---------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    # 统计今日发包总金额、活跃人数、总发包数量
    button1 = InlineKeyboardButton("上一页", callback_data="laturn_%s_2" % page)
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="laturn_%s_1" % page)
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    dispatcher.add_handler(CallbackQueryHandler(laturn, pattern='^laturn_%s_2' % page))
    dispatcher.add_handler(CallbackQueryHandler(laturn, pattern='^laturn_%s_1' % page))
    session.close()


def oper(update, context):
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    args = context.args
    if len(args) <= 0 or len(args) > 2:
        context.bot.send_message(chat_id=chat_id, text="请输入正确指令！")
        return
    if args:
        if args[0] not in ["1", "2", "3"]:
            context.bot.send_message(chat_id=chat_id, text="请输入正确指令！")
            return
        if test_str(args[1]) or find_str(args[1]):
            context.bot.send_message(chat_id=chat_id, text="请输入正确指令！")
            return
    else:
        context.bot.send_message(chat_id=chat_id, text="请输入正确指令！")
        return

    res_dic = {"1": "1", "2": "0", "3": "2"}
    button_dic = {"1": "出雷", "2": "没雷", "3": "随机"}
    value = res_dic.get(args[0], "2")
    t_id = args[1]
    session = Session()
    session.expire_all()
    session.commit()
    try:
        user = session.query(User).filter_by(t_id=t_id).first()
    except Exception as e:
        context.bot.send_message(chat_id, "🚫操作失败🚫")
        session.close()
        return
    user.button = value
    try:
        session.add(user)
        session.commit()
    except Exception as e:
        context.bot.send_message(chat_id, "🚫操作失败🚫")
        session.close()
        return
    context.bot.send_message(chat_id, "操作成功！当前状态为：%s" % button_dic.get(args[0]))


def usersturn(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    message_id = query.message.message_id
    callback_data = query.data
    info = callback_data.split("_")
    now_page = int(info[1])
    status = info[2]  # 2是上一页，1是下一页
    if int(now_page) == 1 and int(status) == 2:
        query.answer("已经在第一页了！", show_alert=True)
        return
    if int(status) == 2:
        page = now_page - 1
    else:
        page = now_page + 1
    page_size = 10

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(User).count()
    except Exception as e:
        print(e)
        return
    # 查询发包列表记录
    try:
        r_objs = session.query(User).order_by(User.time.desc()).offset((page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    button_dic = {"0": "没雷", "1": "出雷", "2": "随机"}
    text = ""
    for obj in r_objs:
        name = obj.name
        invite_lj = obj.invite_lj
        time2 = str(obj.time)
        balance = round(Decimal(obj.balance) / 100, 2)
        firstname = obj.firstname
        t_id = obj.t_id
        low = obj.low
        parent = obj.parent
        button = obj.button
        text += "用户名：<code>%s</code>；\n邀请码：<code>%s</code>；\n余额：<b>%s USDT</b>；\n昵称：<b>%s</b>；\n注册时间：<b>%s</b>；\ntgid：<code>%s</code>；\n下级人数：<b>%s 位</b>；\n上级邀请码：<code>%s</code>\n当前用户雷开关：<b>%s</b>\n" % (
            name, invite_lj, balance, firstname, time2, t_id, low, parent, button_dic.get(button))
        text += "-----------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    # 统计今日发包总金额、活跃人数、总发包数量
    button1 = InlineKeyboardButton("上一页", callback_data="usersturn_%s_2" % page)
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="usersturn_%s_1" % page)
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=ParseMode.HTML,
                                  reply_markup=keyboard)
    dispatcher.add_handler(CallbackQueryHandler(usersturn, pattern='^usersturn_%s_2' % page))
    dispatcher.add_handler(CallbackQueryHandler(usersturn, pattern='^usersturn_%s_1' % page))
    session.close()


def users(update, context):
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    args = context.args
    page = 1
    page_size = 10
    if args:
        try:
            page = int(args[0])
        except Exception as e:
            context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
            return
    if page <= 0 or page >= 999999:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的页数！")
        return

    session = Session()
    session.expire_all()
    session.commit()
    try:
        total_num = session.query(User).count()
    except Exception as e:
        print(e)
        return
    try:
        r_objs = session.query(User).order_by(User.time.desc()).offset((page - 1) * page_size).limit(
            page_size).all()
    except Exception as e:
        print(e)
        return
    page_count = (total_num + page_size - 1) // page_size
    button_dic = {"0": "没雷", "1": "出雷", "2": "随机"}
    text = ""
    for obj in r_objs:
        name = obj.name
        invite_lj = obj.invite_lj
        time2 = str(obj.time)
        balance = round(Decimal(obj.balance) / 100, 2)
        firstname = obj.firstname
        t_id = obj.t_id
        low = obj.low
        parent = obj.parent
        button = obj.button
        text += "用户名：<code>%s</code>；\n邀请码：<code>%s</code>；\n余额：<b>%s USDT</b>；\n昵称：<b>%s</b>；\n注册时间：<b>%s</b>；\ntgid：<code>%s</code>；\n下级人数：<b>%s 位</b>；\n上级邀请码：<code>%s</code>\n当前用户雷开关：<b>%s</b>\n" % (
            name, invite_lj, balance, firstname, time2, t_id, low, parent, button_dic.get(button))
        text += "-----------------\n"
    text += "总页数为：<b>%s</b>，每页最多显示<b>%s</b>条数据" % (page_count, page_size)
    # 统计今日发包总金额、活跃人数、总发包数量
    button1 = InlineKeyboardButton("上一页", callback_data="usersturn_%s_2" % page)
    button2 = InlineKeyboardButton(str(page), callback_data="next")
    button3 = InlineKeyboardButton("下一页", callback_data="usersturn_%s_1" % page)
    row1 = [button1, button2, button3]
    keyboard = InlineKeyboardMarkup([row1])
    context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    dispatcher.add_handler(CallbackQueryHandler(usersturn, pattern='^usersturn_%s_2' % page))
    dispatcher.add_handler(CallbackQueryHandler(usersturn, pattern='^usersturn_%s_1' % page))
    session.close()


def search_user(update, context):
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")
    args = context.args
    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return

    if not args:
        context.bot.send_message(chat_id=chat_id, text="命令使用模板：/查用户 t_id")
        return
    try:
        t_id = int(args[0])
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的用户id！")
        return

    session = Session()
    session.expire_all()
    session.commit()
    try:
        obj = session.query(User).filter_by(t_id=t_id).first()
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=chat_id, text="查询出错！")
        session.close()
        return
    if not obj:
        context.bot.send_message(chat_id=chat_id, text="用户不存在！")
        session.close()
        return
    button_dic = {"0": "没雷", "1": "出雷", "2": "随机"}
    text = ""
    name = obj.name
    invite_lj = obj.invite_lj
    time2 = str(obj.time)
    balance = round(Decimal(obj.balance) / 100, 2)
    firstname = obj.firstname
    t_id = obj.t_id
    low = obj.low
    parent = obj.parent
    button = obj.button
    # 查询该用户所获得过的奖励信息

    try:
        total_reward = session.query(func.sum(cast(Reward_li.reward_money, Numeric))).filter(
            Reward_li.t_id == t_id).first()
    except Exception as e:
        print(e)
        return
    if not total_reward[0]:
        total_reward = [0]
    try:
        total_reward = round((total_reward[0] / 100), 2)
    except Exception:
        return
    text += "用户名：<code>%s</code>；\n邀请码：<code>%s</code>；\n余额：<b>%s USDT</b>；\n昵称：<b>%s</b>；\n注册时间：<b>%s</b>；\ntgid：<code>%s</code>；\n下级人数：<b>%s</b>；\n豹子与顺子总奖励：<b>%s USDT</b>\n上级邀请码：<code>%s</code>\n当前用户雷开关：<b>%s</b>\n" % (
        name, invite_lj, balance, firstname, time2, t_id, low, total_reward, parent, button_dic.get(button))
    button_lei = InlineKeyboardButton("发包全雷", callback_data="kailei_%s_%s" % (obj.t_id, 1))
    button_mei = InlineKeyboardButton("发包没雷", callback_data="kailei_%s_%s" % (obj.t_id, 0))
    button_sui = InlineKeyboardButton("发包随机", callback_data="kailei_%s_%s" % (obj.t_id, 2))
    b_row_1 = [button_lei, button_mei, button_sui]
    keyboard = InlineKeyboardMarkup([b_row_1])
    context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    dispatcher.add_handler(CallbackQueryHandler(kailei, pattern='^kailei*'))
    session.close()


# 查询用户当日报表 /user_report tid
def user_report_today(update, context):
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")
    Chou = float(global_data.get("Chou"))
    Dai_chou = float(global_data.get("Dai_chou"))
    language = global_data.get("language")
    New_reward = global_data.get("New_reward")
    today = datetime.now().date()
    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    args = context.args
    if not args:
        return
    try:
        t_id = int(args[0])
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的用户id！")
        return

    session = Session()
    session.expire_all()
    session.commit()

    print("用户id为：%s" % t_id)
    try:
        user = session.query(User).filter_by(t_id=t_id).first()
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=chat_id, text=Text_data[language]["search_false"])
        session.close()
        return
    if not user:
        user = register(update)
        if not user:
            context.bot.send_message(chat_id=chat_id, text=Text_data[language]["search_false"])
            session.close()
            return
    user_id = user.id

    try:
        r_objs = session.query(Record).filter(Record.send_tid == user.t_id,
                                              func.cast(Record.create_time, Date) == today).all()
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=chat_id, text=Text_data[language]["search_false"])
        session.close()
        return
    # 发包支出
    zhichu = 0
    # 发包盈利
    yingli = 0
    for robj in r_objs:
        if robj.money:
            # 发包金额
            zhichu += robj.money / 100
        if robj.profit:
            # 发包盈利
            yingli += robj.profit

    # 我发包玩家中雷上级代理抽成
    lei_chou = 0
    # 我发包玩家中雷平台抽成
    pingtai_chou = 0
    try:
        sn_objs = session.query(Snatch).filter(Snatch.send_tid == user.t_id,
                                               func.cast(Snatch.create_time, Date) == today, Snatch.status == 1).all()
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=chat_id, text=Text_data[language]["search_false"])
        session.close()
        return
    for sn_obj in sn_objs:
        if user.parent:
            lei_chou += (abs(sn_obj.profit) / 100) * Chou * Dai_chou
        pingtai_chou += (abs(sn_obj.profit) / 100) * Chou

    # 抢包收入
    snatch_shou = 0
    # 抢包中雷赔付
    snatch_lei_lose = 0

    try:
        sn_objs = session.query(Snatch).filter(Snatch.t_id == user.t_id,
                                               func.cast(Snatch.create_time, Date) == today).all()
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=chat_id, text=Text_data[language]["search_false"])
        session.close()
        return
    for sn_obj in sn_objs:
        # 抢包收入
        snatch_shou += (sn_obj.money / 100)
        if sn_obj.status == 1:
            # 抢包中雷赔付
            snatch_lei_lose += (abs(sn_obj.profit) / 100)

    # 邀请返利
    invite_money = 0
    try:
        in_objs = session.query(Holding).filter(Holding.parent == user.t_id,
                                                func.cast(Holding.create_time, Date) == today).all()
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=chat_id, text=Text_data[language]["search_false"])
        session.close()
        return
    invite_money += len(in_objs) * (New_reward / 100)

    # 下级中雷返点
    try:
        logs = session.query(Return_log).filter(Return_log.create_id == user_id,
                                                func.cast(Return_log.create_time, Date) == today).all()
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=chat_id, text=Text_data[language]["search_false"])
        session.close()
        return
    low_lei_fan = 0
    for log in logs:
        low_lei_fan += int(log.money)

    # 奖励所得
    try:
        total_reward = session.query(func.sum(cast(Reward_li.reward_money, Numeric))).filter(
            func.DATE(Reward_li.create_time) == today).first()
    except Exception as e:
        print(e)
        return
    if not total_reward[0]:
        total_reward = [0]
    try:
        total_reward = round((total_reward[0] / 100), 2)
    except Exception:
        return

    content = Text_data['cn']["today_record"] % (
        user.t_id, zhichu, yingli, round(lei_chou, 2), round(pingtai_chou, 2), round(snatch_shou, 2),
        round(snatch_lei_lose, 2), invite_money, round(low_lei_fan, 2), total_reward)
    context.bot.send_message(chat_id=chat_id, text=content, parse_mode=ParseMode.HTML)


# 管理员命令面板 /admin_help
def admin_help(update, context):
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    content = """<code>/cz t_id money</code>  管理员指定用户id上分\n<code>/xf t_id money</code>  管理员指定用户id下分\n<code>/users (page)</code>  查看用户列表\n<code>/today</code>  查看平台今日报表\n<code>/month</code>  查看平台今月报表\n<code>/recharge_list (成功) (page)</code>  查看充值列表（命令后面输入{取消,成功,超时}可进行状态筛选）\n<code>/recharge_user t_id (page)</code>  查看指定用户充值记录\n<code>/wthdrawal_list (page)</code>  查看下分列表\n<code>/wthdrawal_user t_id (page)</code>  查看指定用户下分记录\n<code>/fa_list (page)</code>  查看用户发包列表\n<code>/qiang_list (page)</code>  查看用户抢包列表\n<code>/la_list (page)</code>  查看拉人列表\n<code>/user_report_today t_id</code>  查看指定用户今日报表\n<code>/change_lan 英文</code>  切换语言类型\n<code>/cx t_id</code>  查询指定用户信息\n<code>/gly</code>  查询管理员ID列表\n<code>/add t_id</code>  添加管理员\n<code>/del t_id</code>  删除管理员\n<code>/fa_user t_id (page)</code>  查询指定用户发包记录\n<code>/qiang_user t_id (page)</code>  查询指定用户抢包记录\n<b>注意：括号内参数可不传，t_id代表用户id，money代表金额，page代表页数</b>\n"""

    context.bot.send_message(chat_id=chat_id, text=content, parse_mode=ParseMode.HTML)


def change_lan(update, context):
    user_id = update.message.from_user["id"]
    chat_id = update.message.chat.id
    global global_data
    Admin_li = global_data.get("Admin_li")

    if str(user_id) not in Admin_li and str(chat_id) not in Admin_li:
        print(user_id)
        return
    # 切换语言
    name_dic = {"中文": "cn", "英文": "en"}
    args = context.args
    if not args:
        return
    try:
        lang2 = args[0]
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的语言类型！（中文或英文）")
        return
    lang = name_dic.get(lang2)
    if not lang:
        context.bot.send_message(chat_id=chat_id, text="请输入正确的语言类型！（中文或英文）")
        return
    session = Session()
    session.expire_all()
    session.commit()
    # try:
    #     obj = session.query(Conf).filter_by(name='language').first()
    # except Exception as e:
    #     print(e)
    #     context.bot.send_message(chat_id=chat_id, text="切换语言失败")
    #     session.close()
    #     return
    # if not obj:
    #     context.bot.send_message(chat_id=chat_id, text="切换语言失败")
    #     session.close()
    #     return
    # obj.value = lang
    # try:
    #     session.add(obj)
    #     session.commit()
    # except Exception as e:
    #     print(e)
    #     session.rollback()
    #     session.close()
    #     context.bot.send_message(chat_id=chat_id, text="切换语言失败")
    #     return
    global_data["language"] = lang
    print(global_data)
    context.bot.send_message(chat_id=chat_id, text="切换语言成功！\n当前语言类型为：%s" % lang2)


def get_id(update, context):
    chat_id = update.message.chat.id
    context.bot.send_message(chat_id=chat_id, text=str(chat_id))


class Spider():
    def __init__(self, wallet):
        self.url = "https://api.trongrid.io/v1/accounts/%s/transactions/trc20?only_to=true&limit=20&contract_address=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t" % wallet
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/112.0.0.0 Safari/537.36",
        }
        self.proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
        self.result = []

    def parse(self):
        try:
            # data = json.loads(requests.get(self.url, headers=self.headers, proxies=self.proxies).content.decode())
            data = json.loads(requests.get(self.url, headers=self.headers).content.decode())
        except Exception as e:
            print("请求转账信息失败！")
            return 0
        for line in data.get("data", []):
            self.result.append(line)
        if not self.result:
            return 0
        return 1

    def run(self):
        if self.parse():
            print("获取数据成功！")
            return self.result
        return []


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


def update_wallte():
    session = get_session()
    # 查询当前监听的钱包地址
    myaddress = global_data.get("My_address", "TAZ5gPwfU4bn14dKRqJXbCZJGJMqgoJsaf")
    spider = Spider(myaddress)
    result = spider.run()
    print("当前监听钱包地址为：", myaddress)
    for line in result:
        # 2.判断数据是否在数据库中
        order_id = line.get("transaction_id", "")
        block_timestamp = line.get("block_timestamp", "")
        if block_timestamp:
            create_time = timestr_to_time(block_timestamp / 1000)
            # print("钱包转账时间：%s" % create_time)
        else:
            create_time = None
        if line["type"] != "Transfer":
            continue
        print("该笔订单交易类型为：", line["type"])
        try:
            obj = session.query(Wallet).filter_by(id=order_id).first()
        except Exception as e:
            print(e)
            continue
        if obj:

            continue
        money = int(line.get("value"))
        sender = line.get("from")
        recipient = line.get("to")
        print(sender)
        try:
            obj = Wallet(id=order_id, money=money, sender=sender, recipient=recipient, create_time=create_time,
                         insert_time=datetime.now())
        except Exception as e:
            print(e)
            session.rollback()
            session.close()
            continue
        # 3.入库
        try:
            session.add(obj)
            session.commit()
        except Exception as e:
            print(e)
            session.rollback()
    session.close()


def update_wallet_task():
    while True:
        # 读取数据库数据
        session = Session()
        session.expire_all()
        session.commit()
        try:
            orders = session.query(Recharge).options(joinedload('*')).filter_by(status=2).all()
        except Exception as e:
            print(e)
            orders = []
        if not orders:
            time.sleep(30)
            session.close()
            continue
        # 更新钱包记录
        update_wallte()
        for order in orders:
            # 订单金额
            money = str(int(Decimal(order.money) * 1000000))
            print("订单金额为：", money)
            # tg的id
            t_id = order.t_id
            # 订单创建时间
            create_time = order.create_time
            delta = timedelta(minutes=10)
            print("订单创建时间为：%s" % create_time)
            end_date = create_time + delta
            print("订单截止时间为：%s" % end_date)
            now = datetime.now()
            if now > end_date:
                print("订单已超时！并且设置了订单为超时状态。")
                # 设置订单状态为已超时
                order.status = 3
                try:
                    session.add(order)
                    session.commit()
                except Exception as e:
                    print(e)
                    session.rollback()
                continue
            # 通过订单金额去匹配钱包记录
            try:
                obj = session.query(Wallet).options(joinedload('*')).filter(
                    Wallet.money == money, Wallet.create_time.between(create_time, end_date)).first()
            except Exception as e:
                print(e)
                continue
            if not obj:
                print("没有匹配的订单")
                continue
            # 设置充值成功，根据tgid定位用户，给用户添加余额
            try:
                user = session.query(User).options(joinedload('*')).filter_by(t_id=t_id).first()
            except Exception as e:
                print(e)
                continue
            if not user:
                continue
            num = Decimal(order.money)
            print("充值前用户余额为：%s" % user.balance)
            user.balance = Decimal(user.balance) + num
            print("充值后用户余额为：%s" % user.balance)
            order.status = 1
            flag = 1
            try:
                session.add(user)
                session.add(order)
                session.commit()
            except Exception as e:
                print(e)
                session.rollback()
                flag = 2
            if flag == 1:
                print("充值成功！")
            else:
                print("充值失败")
                order.status = 0
                try:
                    session.add(order)
                    session.commit()
                except Exception as e:
                    session.rollback()
                    continue
        time.sleep(6)
        session.close()


def recycling_expired_task():
    while True:
        Num = global_data.get("Num")
        Bei = Decimal(global_data.get("Bei"))
        Group_id = global_data.get("Group_id")
        Channel_name = global_data.get("Channel_name", "yingsheng001")
        Bot_name = global_data.get("Bot_name", "yinghai_bot")
        language = global_data.get("language", "cn")
        kefu = global_data.get("kefu", "toumingde")
        caiwu = global_data.get("caiwu", "touminde")
        # 读取所有红包（发包了有5分钟的，且小于10分钟的。同时剩余红包不为0的）
        session = Session()
        session.expire_all()
        session.commit()
        # 当前时间
        now = datetime.now()
        # 往前推5分钟
        now_to_five = now - timedelta(minutes=5)
        # 往前推10分钟
        now_to_ten = now - timedelta(minutes=10)
        try:
            r_objs = session.query(Record).filter(
                Record.residue != 0,
                Record.last_fa_time <= now_to_five,
                Record.create_time >= now_to_ten
            ).all()
        except Exception as e:
            print(e)
            r_objs = []
        if not r_objs:
            time.sleep(30)
            session.close()
            pass

        # 重新发送这些红包
        for r_obj in r_objs:
            t_id = r_obj.send_tid
            try:
                user = session.query(User).filter_by(t_id=t_id).first()
            except Exception as e:
                print(e)
                continue
            first_name = user.firstname
            print(r_obj.last_fa_time)
            money = int(r_obj.money / 100)
            lei = r_obj.lei
            photo_path = 'img/%s' % Text_data[language]["pic_name"]
            num = r_obj.residue
            content = Text_data[language]["user_send_pack"] % (first_name, money)
            print(Num - num)
            # 抢红包按钮
            rob_btn = InlineKeyboardButton(Text_data[language]["rob_button"] % (Num, Num - num, money, lei),
                                           callback_data='rob_%s_%s_%s_%s' % (r_obj.id, money, lei, 1))
            buttons_row1 = [rob_btn]
            button = InlineKeyboardButton(Text_data[language]["kefu"], url="https://t.me/%s" % kefu)
            button1 = InlineKeyboardButton(Text_data[language]["recharge"], url="https://t.me/%s" % caiwu)
            button2 = InlineKeyboardButton(Text_data[language]["wanfa"], url="https://t.me/%s" % Channel_name)
            button3 = InlineKeyboardButton(Text_data[language]["balance"], callback_data="yue")
            # 将四个按钮放在一个列表中作为一行的按钮列表
            buttons_row2 = [button, button1, button2, button3]
            button4 = InlineKeyboardButton(Text_data[language]["tuiguang_search"], callback_data="promote_query")
            button5 = InlineKeyboardButton(Text_data[language]["today_record_btn"], callback_data="today_record")
            buttons_row3 = [button4, button5]
            keyboard = InlineKeyboardMarkup([buttons_row1, buttons_row2, buttons_row3])
            dispatcher.add_handler(CallbackQueryHandler(alert, pattern='^promote_query'))
            dispatcher.add_handler(CallbackQueryHandler(today_record, pattern='^today_record'))
            dispatcher.add_handler(CallbackQueryHandler(yue, pattern='^yue'))
            # 第一个是记录ID
            # 第二个是红包金额
            # 第三个是雷
            # 第四个表示第几个红包
            dispatcher.add_handler(CallbackQueryHandler(rob, pattern='^rob_%s_%s_%s_%s' % (r_obj.id, money, lei, 1)))
            dispatcher.add_handler(CallbackQueryHandler(alert, pattern='^promote_query'))
            dispatcher.add_handler(CallbackQueryHandler(yue, pattern='^yue'))
            r_obj.last_fa_time = datetime.now()
            try:
                session.add(user)
                session.add(r_obj)
                session.commit()
                updater.bot.send_photo(Group_id, caption=content, photo=open(photo_path, 'rb'),
                                       parse_mode=ParseMode.HTML, reply_markup=keyboard)
            except Exception as e:
                print(e)
                session.rollback()
                session.close()
                updater.bot.send_message(Group_id, Text_data[language]["send_false"])

        try:
            r_objs = session.query(Record).filter(
                Record.residue != 0,
                Record.create_time < now_to_ten
            ).all()
        except Exception as e:
            print(e)
            r_objs = []
        if not r_objs:
            time.sleep(30)
            session.close()
            continue
        print("当前有%s个需要回收红包！" % len(r_objs))
        for r_obj in r_objs:
            t_id = r_obj.send_tid
            try:
                user = session.query(User).filter_by(t_id=t_id).first()
            except Exception as e:
                print(e)
                continue
            num = r_obj.residue
            result = json.loads(r_obj.result)
            # 获取该红包剩余金额
            return_money = sum(result[:num])
            print("需要回收发放的红包金额为：", return_money)
            print("红包ID为：", r_obj.id)
            print("用户余额为：", user.balance)
            user.balance = Decimal(user.balance) + return_money
            r_obj.residue = 0
            # 查询出该记录的所有抢包结果
            try:
                objs = session.query(Snatch).filter_by(r_id=r_obj.id).all()
            except Exception as e:
                session.rollback()
                continue
            flag = 1
            # 总盈利
            total = 0
            # 包主实收
            for line in objs:
                # 金额
                l_money = line.money
                # 昵称
                firstname = line.firstname
                # 状态
                status = line.status
                # 盈利
                profit = line.profit
                if profit < 0:
                    # 说明包主盈利了
                    total += abs(profit)
                flag += 1
            r_obj.profit = (total / 100)
            # 包主实际收入 发了100U 正常来说是赚200U 但是有雷没人抢，现在被回收了
            r_obj.received = ((total / 100) + return_money - r_obj.money)
            try:
                session.add(user)
                session.add(r_obj)
                session.commit()
            except Exception as e:
                print(e)
                session.rollback()
                continue
        time.sleep(30)


def recycle_address():
    global global_data
    # 一小时轮换一次钱包地址
    while True:
        All_address = global_data["All_address"]
        for address in All_address:
            session = Session()
            session.expire_all()
            session.commit()
            # 判断当前是否有充值订单
            try:
                r_obj = session.query(Recharge).filter_by(status=2).all()
            except Exception as e:
                print(e)
                session.close()
                time.sleep(3600)
                continue
            if r_obj:
                session.close()
                time.sleep(3600)
                continue
            global_data["My_address"] = address
            time.sleep(3600)
            continue


# 用户命令功能
dispatcher.add_handler(CommandHandler('id', get_id))
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('help', send_help))
dispatcher.add_handler(CommandHandler('invite', invite))
dispatcher.add_handler(CommandHandler('wanfa', wanfa))
dispatcher.add_handler(CommandHandler('recharge', recharge))
dispatcher.add_handler(CommandHandler('admin_help', admin_help))

# 管理员操作命令功能
dispatcher.add_handler(CommandHandler('cz', adminrecharge))
dispatcher.add_handler(CommandHandler('add', add_admin))
dispatcher.add_handler(CommandHandler('gly', admin_list))
dispatcher.add_handler(CommandHandler('del', del_admin))
dispatcher.add_handler(CommandHandler('xf', xiafen))
dispatcher.add_handler(CommandHandler('update', update_env))
dispatcher.add_handler(CommandHandler('change_lan', change_lan))

# 管理员查询命令功能
# 用户列表
dispatcher.add_handler(CommandHandler('users', users))
# 查询指定用户信息
dispatcher.add_handler(CommandHandler('cx', search_user))
# 今日报表
dispatcher.add_handler(CommandHandler('today', today_data))
# 今月报表
dispatcher.add_handler(CommandHandler('month', month_data))
# 充值列表
dispatcher.add_handler(CommandHandler('recharge_list', recharge_list))
# 单个用户充值记录
dispatcher.add_handler(CommandHandler('recharge_user', recharge_user))
# 提现列表
dispatcher.add_handler(CommandHandler('wthdrawal_list', wthdrawal_list))
# 单个用户提现记录
dispatcher.add_handler(CommandHandler('wthdrawal_user', wthdrawal_user))
# 用户发包记录
dispatcher.add_handler(CommandHandler('fa_list', fa_list))
# 单个用户发包记录
dispatcher.add_handler(CommandHandler('fa_user', fa_user))
# 用户抢包记录
dispatcher.add_handler(CommandHandler('qiang_list', qiang_list))
# 单个用户抢包记录
dispatcher.add_handler(CommandHandler('qiang_user', qiang_user))
# 用户拉人记录
dispatcher.add_handler(CommandHandler('la_list', la_list))
# 开关发包结果
dispatcher.add_handler(CommandHandler('oper', oper))
# 指定用户报表（今日、今月）
dispatcher.add_handler(CommandHandler('user_report_today', user_report_today))

# 监听发红包
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_user_reply))

t2 = threading.Thread(target=update_wallet_task)
t2.start()

t3 = threading.Thread(target=recycling_expired_task)
t3.start()

t4 = threading.Thread(target=recycle_address)
t4.start()

if __name__ == '__main__':
    print('开始运行机器人.....')
    try:
        updater.start_polling()
        updater.idle()
    except KeyboardInterrupt:
        updater.stop()
