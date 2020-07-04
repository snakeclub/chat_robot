#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# peewee 中文参考：https://www.osgeo.cn/peewee/index.html

"""
答案库的操作模块
@module answer_db
@file answer_db.py
"""

import os
import sys
import datetime
import peewee as pw
from playhouse.pool import PooledMySQLDatabase, PooledPostgresqlDatabase, PooledSqliteDatabase
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))


__MOUDLE__ = 'answer_db'  # 模块名
__DESCRIPT__ = u'答案库的操作模块'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.06.22'  # 发布日期


DB_PROXY = pw.Proxy()  # 数据库代理，用于在运行时指定或切换数据库


# 数据库模型定义
class BaseModel(pw.Model):
    """
    数据库基础模型，定义数据库对象使用代理
    """
    class Meta:
        database = DB_PROXY


class Answer(BaseModel):
    """
    答案管理的数据库模型
    """
    std_question_id = pw.BigIntegerField(primary_key=True)  # 标准问题ID
    a_type = pw.CharField(
        choices=[('text', '文字答案'), ('job', '执行任务'), ('options', '选项'), ('ask', '上下文问题')],
        default='text',
    )  # 答案类型
    type_param = pw.CharField(max_length=4000, default='')  # 答案类型扩展参数
    replace_pre_def = pw.CharField(default='N')  # 替换预定义字符
    answer = pw.CharField(max_length=4000)  # 答案描述字段

    class Meta:
        # 定义数据库表名
        table_name = 'answers'


class StdQuestion(BaseModel):
    """
    标准问题清单
    """
    id = pw.BigAutoField()  # 自增字段
    q_type = pw.CharField(
        choices=[('ask', '问答类'), ('context', '场景类')],
        default='ask',
    )  # 问题类型, ask-问答类（问题对应答案），context-场景类（问题对应上下文场景）
    milvus_id = pw.BigIntegerField(index=True)  # milvus向量ID
    collection = pw.CharField()  # 问题所属分类集
    partition = pw.CharField(default='')  # 问题所属场景
    question = pw.CharField(max_length=4000)  # 问题描述字段

    class Meta:
        # 定义数据库表名
        table_name = 'std_questions'
        indexes = (
            # 多列唯一索引
            (('milvus_id', 'collection', 'partition'), False),
        )


class ExtQuestion(BaseModel):
    """
    扩展问题清单（标准问题的其他问法）
    """
    id = pw.BigAutoField()  # 自增字段
    milvus_id = pw.BigIntegerField(index=True)  # milvus向量ID
    std_question_id = pw.BigIntegerField()  # 对应的标准问题ID
    question = pw.CharField(max_length=4000)  # 问题描述字段

    class Meta:
        # 定义数据库表名
        table_name = 'ext_questions'
        indexes = (
            # 多列唯一索引
            (('milvus_id', 'std_question_id'), True),
        )


class CollectionOrder(BaseModel):
    """
    搜索分类排序，在未指定分类的情况下，按该排序优先搜索答案
    """
    collection = pw.CharField(primary_key=True)  # 问题所属分类集
    order_num = pw.SmallIntegerField()  # 问题排序，数字越大越在前面
    remark = pw.CharField(max_length=4000, default='')  # 备注信息

    class Meta:
        # 定义数据库表名
        table_name = 'collection_order'


class NoMatchAnswers(BaseModel):
    """
    未匹配上问题记录
    """
    id = pw.BigAutoField()  # 自增字段
    session_info = pw.CharField(max_length=4000, default='')
    question = pw.CharField(max_length=4000)  # 未匹配到的问题
    create_time = pw.DateTimeField(default=datetime.datetime.now)  # 创建时间

    class Meta:
        # 定义数据库表名
        table_name = 'no_match_answers'


class CommonPara(BaseModel):
    """
    通用参数
    """
    para_name = pw.CharField(primary_key=True)  # 参数名
    para_value = pw.CharField(max_length=4000)  # 参数值
    remark = pw.CharField(max_length=4000, default='')  # 备注信息

    class Meta:
        # 定义数据库表名
        table_name = 'common_para'


class NlpSureJudgeDict(BaseModel):
    """
    nlp模块肯定/否定判断字典
    """
    word = pw.CharField(index=True)  # 判断词
    sign = pw.CharField(
        choices=[('sure', '肯定'), ('negative', '否定')],
        default='sure',
    )  # 判断类型
    word_class = pw.CharField()  # 词性，例如eng、m、x等

    class Meta:
        # 定义数据库表名
        table_name = 'nlp_sure_judge_dict'
        indexes = (
            # 多列唯一索引
            (('word', 'word_class'), True),
        )


class NlpPurposConfigDict(BaseModel):
    """
    nlp模块意图配置字典
    """
    action = pw.CharField(index=True)  # 匹配动作
    collection = pw.CharField()  # 搜索问题所属分类集
    partition = pw.CharField(default='')  # 搜索问题所属场景
    std_question_id = pw.BigIntegerField()  # 意图对应的标准问题ID
    order_num = pw.IntegerField()  # 匹配排序，越大排序越高
    # 意图信息的获取处理函数配置，格式为 [class_name, fun_name, {para_dict}]
    info = pw.CharField(max_length=4000, default='[]')

    class Meta:
        # 定义数据库表名
        table_name = 'nlp_purpos_config_dict'
        indexes = (
            # 多列唯一索引
            (('action', 'collection', 'partition'), True),
        )


# 重定义数据库对象
class ReconnectMixin(object):
    """
    支持失败重新连接数据库的处理类
    """
    # 重连接的错误列表，需要继承类重载，格式为((错误信息类type, 错误信息str), ... )
    reconnect_errors = tuple()

    def __init__(self, *args, **kwargs):
        super(ReconnectMixin, self).__init__(*args, **kwargs)

        # Normalize the reconnect errors to a more efficient data-structure.
        self._reconnect_errors = {}
        for exc_class, err_fragment in self.reconnect_errors:
            self._reconnect_errors.setdefault(exc_class, [])
            self._reconnect_errors[exc_class].append(err_fragment.lower())

    def execute_sql(self, sql, params=None, commit=pw.SENTINEL):
        try:
            return super(ReconnectMixin, self).execute_sql(sql, params, commit)
        except Exception as exc:
            exc_class = type(exc)
            if exc_class not in self._reconnect_errors:
                raise exc

            exc_repr = str(exc).lower()
            for err_fragment in self._reconnect_errors[exc_class]:
                if err_fragment in exc_repr:
                    break
            else:
                raise exc

            if not self.is_closed():
                self.close()
                self.connect()

            return super(ReconnectMixin, self).execute_sql(sql, params, commit)


class RetryPooledMySQLDatabase(ReconnectMixin, PooledMySQLDatabase):
    """
    支持错误重连接的连接池数据库对象
    """
    # 重载重连接错误清单
    reconnect_errors = (
        # Error class, error message fragment (or empty string for all).
        (pw.OperationalError, '2006'),  # MySQL server has gone away.
        (pw.OperationalError, '2013'),  # Lost connection to MySQL server.
        (pw.OperationalError, '2014'),  # Commands out of sync.

        # mysql-connector raises a slightly different error when an idle
        # connection is terminated by the server. This is equivalent to 2013.
        (pw.OperationalError, 'MySQL Connection not available.'),
    )


class RetryPooledPostgresqlDatabase(ReconnectMixin, PooledPostgresqlDatabase):
    """
    支持错误重连接的连接池数据库对象
    """
    # 重载重连接错误清单, 待测试后再增加
    reconnect_errors = tuple()


class RetryPooledSqliteDatabase(ReconnectMixin, PooledSqliteDatabase):
    """
    支持错误重连接的连接池数据库对象
    """
    # 重载重连接错误清单, 待测试后再增加
    reconnect_errors = tuple()


class AnswerDao(object):
    """
    答案库访问对象类
    """

    #############################
    # 工具函数
    #############################
    @classmethod
    def get_database(cls, connect_para: dict):
        """
        初始化数据库访问类

        @param {dict} connect_para - 连接参数，传入server.xml的answerdb节点字典
            db_type {str} - 数据库类型，默认MySQL
            database {str} - 要使用的数据库实例名
            max_connections {int} - 连接池最大连接数量，默认20
            stale_timeout {float} - 允许使用连接的时间(秒)
            timeout {float} - 当获取不到新连接的等待超时时间(秒)

            MySQL的连接参数：
                host {str} - 服务器地址，默认127.0.0.1
                port {int} - 服务器端口，默认3306
                user {str} - 登陆用户名
                password {str} - 登陆密码
                connect_timeout {float} - 连接超时时间(秒)
                charset {str} - 字符集，默认utf8

        @returns {PooledDatabase} - 返回生成的连接池数据库对象
        """
        # 从参数中获取关键要素
        _db_type = connect_para.pop('db_type', 'MySQL')
        _database = connect_para.pop('database')

        # 设置数据库连接默认值
        _connect_para = {
            'max_connections': 20,  # 连接池最大连接数量
            'stale_timeout': None,
            'timeout': None
        }
        if _db_type == 'MySQL':
            _db_driver = RetryPooledMySQLDatabase
            _connect_para.update(
                {
                    'host': '127.0.0.1',
                    'port': 3306,
                }
            )
        else:
            raise NotImplementedError('not support db type: %s!' % _db_type)

        _connect_para.update(connect_para)

        # 连接数据库并返回
        _db = _db_driver(_database, **_connect_para)
        return _db

    @classmethod
    def initialize_proxy(cls, db_proxy, database):
        """
        设置数据库代理为指定数据库连接对象

        @param {peewee.Proxy} db_proxy - 数据库代理
        @param {peewee.DataBase} database - 已初始化的数据库对象
        """
        db_proxy.initialize(database)

    @classmethod
    def create_tables(cls, table_model_list: list):
        """
        检查表是否存在，如果不存在则创建表

        @param {list} table_model_list - pw.Model实例对象清单
        """
        for _table in table_model_list:
            if not _table.table_exists():
                _table.create_table()

    @classmethod
    def drop_tables(cls, table_model_list: list):
        """
        检查表是否存在，如果存在则删除表

        @param {list} table_model_list - pw.Model实例对象清单
        """
        for _table in table_model_list:
            if _table.table_exists():
                _table.drop_table()

    #############################
    # 答案库的专用操作
    #############################
    @classmethod
    def init_answerdb(cls, connect_para: dict):
        """
        装载答案库

        @param {dict} connect_para - 连接参数，传入server.xml的answerdb节点字典
            db_type {str} - 数据库类型，默认MySQL
            database {str} - 要使用的数据库实例名
            max_connections {int} - 连接池最大连接数量，默认20
            stale_timeout {float} - 允许使用连接的时间(秒)
            timeout {float} - 当获取不到新连接的等待超时时间(秒)

            MySQL的连接参数：
                host {str} - 服务器地址，默认127.0.0.1
                port {int} - 服务器端口，默认3306
                user {str} - 登陆用户名
                password {str} - 登陆密码
                connect_timeout {float} - 连接超时时间(秒)
                charset {str} - 字符集，默认utf8

        @returns {DataBase} - 数据库对象
        """
        # 连接数据库
        _db = cls.get_database(connect_para)
        cls.initialize_proxy(DB_PROXY, _db)

        return _db


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))

    import re
    _str = "abc{$id=1$}cde{$id=\'A3\'$}ef"
    print(re.findall(r'\{\$.+?\$\}', _str, re.M))

    print(re.findall(r'\{\$.+?\$1111\}', _str))

    re.search()

    def fun(m):
        print(m.group(0))
        return '{id}'

    print(
        re.sub(r'\{\$.+?\$\}', fun, _str, re.M)
    )
