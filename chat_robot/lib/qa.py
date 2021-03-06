#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
问答处理模块
@module qa
@file qa.py
"""

import os
import sys
import copy
import uuid
import time
import re
import datetime
import threading
import traceback
import milvus as mv
import redis
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.data_manager import QAManager, Answer, StdQuestion, ExtQuestion, NoMatchAnswers, SendMessageQueue, SendMessageHis
from chat_robot.lib.nlp import NLP


__MOUDLE__ = 'qa'  # 模块名
__DESCRIPT__ = u'问答处理模块'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.06.27'  # 发布日期


class QA(object):
    """
    问答处理类
    """

    def __init__(self, qa_manager: QAManager, nlp: NLP, execute_path: str, plugins: dict = {},
                 qa_config: dict = {}, redis_config: dict = {}, logger=None):
        # 基础参数
        self.logger = logger  # 日志对象
        self.qa_manager = qa_manager  # 问答数据管理
        self.nlp = nlp  # Nlp自然语言处理支持
        self.execute_path = execute_path  # 执行路径
        self.use_nlp = qa_config.get('use_nlp', True)  # 是否使用NLP辅助处理意图识别
        self.session_overtime = qa_config.get('session_overtime', 300.0)  # session超时时间(秒)
        self.session_checktime = qa_config.get('session_checktime', 1.0)  # 检查session超时的间隔时间
        self.match_distance = qa_config.get('match_distance', 0.9)  # 匹配向量距离最小值
        self.multiple_distance = qa_config.get('multiple_distance', 0.8)  # 如果匹配不到最优, 多选项匹配距离的最小值
        # 如果匹配不到最优，在同一个问题分类下最多匹配的标准问题数量
        self.multiple_in_collection = qa_config.get('multiple_in_collection', 3)
        self.nprobe = qa_config.get('nprobe', 64)  # 盘查的单元数量(cell number of probe)
        # 当找不到问题答案时搜寻标准问题的milvus id
        self.no_answer_milvus_id = qa_config.get('no_answer_milvus_id', -1)
        # 与no_answer_milvus_id配套使用，指定默认标准问题对应的collection
        self.no_answer_collection = qa_config.get('no_answer_collection', 'chat')
        # 没有设置no_answer_milvus_id时找不到答案将返回该字符串
        self.no_answer_str = qa_config.get('no_answer_str', u'对不起，我暂时回答不了您这个问题')
        self.select_options_tip = qa_config.get('select_options_tip', u'找到了多个匹配的问题，请输入序号选择您的题问:')
        self.select_options_tip_no_session = qa_config.get(
            'select_options_tip_no_session', u'找到了多个匹配的问题, 请参照输入您的题问:')
        self.select_options_out_index = qa_config.get(
            'select_options_out_index', u'请输入正确的问题序号(范围为: 1 - {$len$})，例如输入"1"'
        )
        self.query_send_message_num = qa_config.get('query_send_message_num', 2)

        # 插件plugins函数字典，格式为{'type':{'class_name': {'fun_name': fun, }, },}
        self.plugins = plugins

        # Redis缓存
        self.use_redis = qa_config.get('use_redis', False)
        if self.use_redis:
            # 创建连接池
            _redis_connect_para = redis_config.get('connection', {})
            _redis_connect_para['max_connections'] = redis_config.get('pool_size', None)
            _redis_connect_para['decode_responses'] = True  # 这个必须设置为True，确保取到的值是解码后的值
            self.redis_pool = redis.ConnectionPool(
                **_redis_connect_para
            )

            # 删除无效的session
            self.delete_unuse_sessions()

        # 客户连接session管理, key为session_id，value也是一个dict:
        #   last_time : 最近访问时间，用于判断超时清理缓存
        #   info : session信息字典, 可以用于记录客户的一些信息，例如名字、地址等
        #   context : 上下文信息字典
        #   cache : 缓存信息(可以随意被覆盖，使用时需注意)
        self.sessions = dict()

        # 处理session超时的线程
        self._session_overtime_thread_stop = False  # 超时停止标志
        self._session_overtime_thread = threading.Thread(
            target=self._session_overtime_thread_fun,
            args=(0, ),
            name='Thread-Session-Overtime'
        )
        self._session_overtime_thread.setDaemon(True)
        self._session_overtime_thread.start()

    def __del__(self):
        """
        析构函数
        """
        self._session_overtime_thread_stop = True

    #############################
    # 公共session操作(API)
    #############################
    def generate_session(self, info: dict = {}) -> str:
        """
        生成session, 开始QA对话前执行

        @param {dict} info={} - 传入的客户信息字典

        @returns {str} - session_id
        """
        _session_id = str(uuid.uuid1())
        _session_dict = {
            'last_time': datetime.datetime.now(),
            'info': copy.deepcopy(info),
            'context': dict(),
            'cache': dict(),
            'context_cache': dict(),
        }

        if self.use_redis:
            # 使用Redis作为缓存
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                # 添加到session清单
                _redis.hset(
                    'chat_robot:session:list', key=_session_id,
                    value='datetime:%s' % _session_dict['last_time'].strftime('%Y-%m-%d %H:%M:%S')
                )

                # 存入字典
                self._add_redis_dict(
                    'chat_robot:session:%s' % _session_id,
                    _session_dict, _redis
                )
        else:
            # 直接添加到字典中
            self.sessions[_session_id] = _session_dict

        self._log_debug('generate session[%s]: %s' % (_session_id, str(_session_dict)))
        return _session_id

    def check_session_exists(self, session_id: str) -> bool:
        """
        检查session是否存在

        @param {str} session_id - session id

        @returns {bool} - 是否存在
        """
        if session_id is None:
            return False

        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                return _redis.hexists(
                    'chat_robot:session:list',
                    session_id
                )
        else:
            return session_id in self.sessions.keys()

    def update_last_time(self, session_id: str):
        """
        更新上次访问时间

        @param {str} session_id - session id
        """
        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                self._add_redis_dict_value(
                    'chat_robot:session:list', session_id, datetime.datetime.now(),
                    _redis
                )
        else:
            self.sessions[session_id]['last_time'] = datetime.datetime.now()

    def update_session_info(self, session_id: str, info: dict):
        """
        更新session中的客户信息
        注意：更新操作只会变更key相同的信息，不删除原有key不相同的信息

        @param {str} session_id - session id
        @param {dict} info - 要更新的信息字典
        """
        if not self.check_session_exists(session_id):
            raise AttributeError('session_id [%s] not exists!')

        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                self._add_redis_dict(
                    'chat_robot:session:%s:info' % session_id,
                    copy.deepcopy(info), _redis
                )
        else:
            self.sessions[session_id]['info'].update(info)

        self._log_debug('update session[%s]: %s' % (session_id, str(info)))

    def delete_session(self, session_id: str):
        """
        清除指定的session

        @param {str} session_id - session id
        """
        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                # 先删除字典清单
                _redis.hdel('chat_robot:session:list', *(session_id,))

                # 删除实际字典
                self._del_redis_dict(
                    'chat_robot:session:%s' % session_id, _redis
                )
        else:
            self.sessions.pop(session_id, None)

        self._log_debug('delete session[%s]' % (session_id,))

    def get_info_dict(self, session_id: str) -> dict:
        """
        获取info信息字典

        @param {str} session_id - session id

        @returns {dict} - 返回的字典
        """
        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                return self._get_redis_dict(
                    'chat_robot:session:%s:info' % session_id, _redis
                )
        else:
            return self.sessions[session_id]['info']

    def get_info_by_key(self, session_id: str, key: str, default=None):
        """
        通过key获取info信息

        @param {str} session_id - session id
        @param {str} key - key值
        @param {object} default=None - 默认值

        @returns {object} - 返回值
        """
        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                return self._get_redis_dict_by_key(
                    'chat_robot:session:%s:info' % session_id, key, _redis,
                    default=default
                )
        else:
            return self.sessions[session_id]['info'].get(key, default)

    def delete_unuse_sessions(self):
        """
        清除无效session，仅redis模式使用
        """
        _prefix = 'chat_robot:session:*'
        _index = len(_prefix) - 1
        with redis.Redis(connection_pool=self.redis_pool) as _redis:
            # 获取session清单
            _session_list = []
            _keys = _redis.keys('chat_robot:session:*')
            for _key in _keys:
                _session_id = _key[_index:]
                if _session_id != 'list' and _session_id.find(':') == -1:
                    _session_list.append(_session_id)

            # 逐个进行删除
            for _session_id in _session_list:
                if not _redis.hexists('chat_robot:session:list', _session_id):
                    self._del_redis_dict(
                        'chat_robot:session:%s' % _session_id, _redis
                    )
                    self._log_debug('delete unuse session [%s]!' % _session_id)

    #############################
    # 服务端上下文操作
    #############################

    def generate_context_id(self) -> str:
        """
        生成context_id

        @returns {str} - 返回一个新的context_id
        """
        return str(uuid.uuid1())

    def clear_session_dict(self, session_id: str, type_key: str):
        """
        清除session字典

        @param {str} session_id - session id
        @param {str} type_key - 要清除的类型，如info、context、cache、context_cache
        """
        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                self._clear_reids_dict(
                    'chat_robot:session:%s:%s' % (session_id, type_key), _redis
                )
        else:
            self.sessions[session_id][type_key].clear()

    def add_options_context(self, session_id: str, options: dict):
        """
        增加选项上下文信息

        @param {str} session_id - 客户的session id
        @param {dict} options - 选项信息字典，字典定义如下：
            data_type = 'options' - 数据类型
            tips {str} - 开始提示信息
            options {list} - 选项清单，每个选项为一个字典
                option_str {str} - 选项显示文本
                std_question_id {int} - 选项对应标准问题id
                index {int} - 选项对应顺序号
        """
        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                # 清除所有上下文
                self._clear_reids_dict('chat_robot:session:%s:context' % session_id, _redis)

                self._add_redis_dict_value(
                    'chat_robot:session:%s:context' % session_id, 'options', options, _redis
                )
        else:
            self.sessions[session_id]['context'].clear()  # 清除所有上下文
            self.sessions[session_id]['context']['options'] = options
        self._log_debug('Session[%s] add options context: %s' % (session_id, str(options)))

    def add_ask_context(self, session_id: str, ask_info: dict):
        """
        增加提问上下文信息

        @param {str} session_id - 客户的session id
        @param {dict} ask_info - 上下文信息，格式为：
            {
                'context_id': 当前提问上下文的临时id,
                'deal_class': 处理提问答案函数类名,
                'deal_fun': 处理提问答案函数名,
                'std_question_id': 上下文中对应的提问问题id,
                'replace_pre_def': 是否答案替换预定义字符
                'collection': 提问答案参数指定的问题分类,
                'partition': 提问答案参数指定的场景标签,
                'param': 调用处理答案函数的扩展参数
            }
        """
        # 如果字典没有uuid，则设置一个新的uuid
        ask_info.setdefault('context_id', self.generate_context_id())
        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                # 清除所有上下文
                self._clear_reids_dict('chat_robot:session:%s:context' % session_id, _redis)
                self._add_redis_dict_value(
                    'chat_robot:session:%s:context' % session_id, 'ask', ask_info, _redis
                )
        else:
            self.sessions[session_id]['context'].clear()  # 清除所有上下文
            self.sessions[session_id]['context']['ask'] = ask_info

        self._log_debug('Session[%s] add ask context: %s' % (session_id, str(ask_info)))

    def get_context_dict(self, session_id: str):
        """
        获取context字典

        @param {str} session_id - session id

        @return {dict} - 上下文字典
        """
        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                return self._get_redis_dict(
                    'chat_robot:session:%s:context' % session_id, _redis
                )
        else:
            return self.sessions[session_id]['context']

    def add_cache(self, session_id: str, key: str, value, context_id: str = None):
        """
        添加缓存信息

        @param {str} session_id - 客户的session id
        @param {str} key - 缓存的key
        @param {object} value - 缓存的值
        @param {str} context_id=None - 指定的上下文id
        """
        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                if context_id is None:
                    self._add_redis_dict_value(
                        'chat_robot:session:%s:cache' % session_id, key, value, _redis
                    )
                else:
                    # 存在上下文id的时候，主动清掉其他上下文的临时信息
                    if not _redis.hexists(
                        'chat_robot:session:%s:context_cache' % session_id, context_id
                    ):
                        self._clear_reids_dict(
                            'chat_robot:session:%s:context_cache' % session_id, _redis
                        )

                    self._add_redis_dict_value(
                        'chat_robot:session:%s:context_cache' % session_id, context_id,
                        {key: value}, _redis
                    )
        else:
            if context_id is None:
                self.sessions[session_id]['cache'][key] = value
            else:
                # 存在上下文id的时候，主动清掉其他上下文的临时信息
                if context_id not in self.sessions[session_id]['context_cache'].keys():
                    self.sessions[session_id]['context_cache'].clear()
                    self.sessions[session_id]['context_cache'][context_id] = dict()
                self.sessions[session_id]['context_cache'][context_id][key] = value

        self._log_debug('Session[%s] context[%s] add cache %s[%s]' %
                        (session_id, context_id, key, str(value)))

    def del_cache(self, session_id: str, key: str, context_id: str = None):
        """
        删除缓存信息

        @param {str} session_id - 客户的session id
        @param {str} key - 缓存的key
        @param {str} context_id=None - 指定的上下文id
        """
        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                if context_id is None:
                    self._del_redis_dict_by_key(
                        'chat_robot:session:%s:cache' % session_id, key, _redis
                    )
                else:
                    self._del_redis_dict_by_key(
                        'chat_robot:session:%s:context_cache:%s' % (session_id, context_id),
                        key, _redis
                    )
        else:
            if context_id is None:
                if key in self.sessions[session_id]['cache'].keys():
                    del self.sessions[session_id]['cache'][key]
            else:
                if context_id in self.sessions[session_id]['context_cache'].keys():
                    if key in self.sessions[session_id]['context_cache'][context_id].keys():
                        del self.sessions[session_id]['context_cache'][context_id][key]

        self._log_debug('Session[%s] context[%s] del cache %s' % (session_id, context_id, key))

    def get_cache_value(self, session_id: str, key: str, default=None, context_id: str = None):
        """
        获取缓存信息

        @param {str} session_id - 客户的session id
        @param {str} key - 缓存的key
        @param {object} default=None - 当获取不到的默认值
        @param {str} context_id=None - 指定的上下文id

        @returns {object} - 返回缓存值
        """
        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                if context_id is None:
                    _value = self._get_redis_dict_by_key(
                        'chat_robot:session:%s:cache' % session_id, key, _redis,
                        default=default
                    )
                else:
                    _value = self._get_redis_dict_by_key(
                        'chat_robot:session:%s:context_cache:%s' % (session_id, context_id),
                        key, _redis, default=default
                    )
        else:
            if context_id is None:
                _value = self.sessions[session_id]['cache'].get(key, default)
            else:
                _value = (self.sessions[session_id]['context_cache']
                          .get(context_id, {})
                          .get(key, default))

        self._log_debug('Session[%s] context[%s] get cache %s[%s]' %
                        (session_id, context_id, key, str(_value)))
        return _value

    def update_cache_dict(self, session_id: str, info: dict, context_id: str = None):
        """
        更新缓存字典信息

        @param {str} session_id - 客户的session id
        @param {dict} info - 要更新的信息字典
        @param {str} context_id=None - 指定的上下文id
        """
        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                if context_id is None:
                    self._add_redis_dict(
                        'chat_robot:session:%s:cache' % session_id, copy.deepcopy(info), _redis
                    )
                else:
                    if not _redis.hexists(
                        'chat_robot:session:%s:context_cache' % session_id, context_id
                    ):
                        self._clear_reids_dict(
                            'chat_robot:session:%s:context_cache' % session_id, _redis
                        )

                    self._add_redis_dict(
                        'chat_robot:session:%s:context_cache' % session_id,
                        {context_id: copy.deepcopy(info)}, _redis
                    )
        else:
            if context_id is None:
                self.sessions[session_id]['cache'].update(info)
            else:
                if context_id not in self.sessions[session_id]['context_cache'].keys():
                    self.sessions[session_id]['context_cache'].clear()
                    self.sessions[session_id]['context_cache'][context_id] = dict()
                self.sessions[session_id]['context_cache'][context_id].update(info)

        self._log_debug('Session[%s] context[%s] update cache dict: %s' %
                        (session_id, context_id, info))

    def get_cache_dict(self, session_id: str, default=None, context_id: str = None) -> dict:
        """
        获取缓存字典

        @param {str} session_id - 客户的session id
        @param {object} default=None - 当获取不到的默认值
        @param {str} context_id=None - 指定的上下文id

        @returns {dict} - 返回缓存字典
        """
        if self.use_redis:
            with redis.Redis(connection_pool=self.redis_pool) as _redis:
                if context_id is None:
                    _dict = self._get_redis_dict(
                        'chat_robot:session:%s:cache' % session_id, _redis
                    )
                else:
                    _dict = self._get_redis_dict(
                        'chat_robot:session:%s:context_cache:%s' % (session_id, context_id),
                        _redis
                    )
        else:
            if context_id is None:
                _dict = self.sessions[session_id]['cache']
            else:
                if context_id not in self.sessions[session_id]['context_cache'].keys():
                    _dict = default
                else:
                    _dict = self.sessions[session_id]['context_cache'][context_id]

        self._log_debug('Session[%s] context[%s] get cache dict: %s' %
                        (session_id, context_id, _dict))

        return _dict

    #############################
    # 公共问答处理
    #############################
    def quession_search(self, question: str, session_id: str = None, collection: str = None,
                        std_question_id: int = None, std_question_tag: str = None) -> list:
        """
        搜寻问题答案并返回

        @param {str} question - 提出的问题
        @param {str} session_id=None - session id
        @param {str} collection=None - 问题分类
        @param {int} std_question_id=None - 指定匹配的标准问题id（如指定后不再进行匹配处理）
        @param {str} std_question_tag=None - 指定匹配的标准问题tag（如指定后不再进行匹配处理）

        @returns {list} - 返回的问题答案字符数组，有可能是多个答案
            注意：返回的清单如果第1个对象类型是str，则属于文本返回；如果第1个对象的类型是dict(且只允许一个)，则数据json数据返回
        """
        # 检查session是否存在
        if not self.check_session_exists(session_id):
            raise FileNotFoundError('session id [%s] not exists!' % session_id)

        # 更新上次访问时间
        self.update_last_time(session_id)

        # 根据上下文及传参， 设置collection、partition及
        _collection, _partition, _match_list, _answer, _context_id = self._pre_deal_context(
            question, session_id, collection, std_question_id, std_question_tag
        )

        if _answer is not None:
            return _answer

        if _match_list is None and self.use_nlp:
            # 使用NLP语义解析尝试匹配意图
            _collection, _partition, _match_list, _answer = self._nlp_match_action(
                question, session_id, _collection, _partition
            )

        if _match_list is None:
            # 查询标准问题及答案
            with self.qa_manager.get_bert_client() as _bert, self.qa_manager.get_milvus() as _milvus:
                _vectors = _bert.encode([question, ])
                _question_vector = self.qa_manager.normaliz_vec(_vectors.tolist())[0]

                # 进行匹配
                if _collection is None and _partition is None:
                    # 查询多个问题分类的结果清单
                    _match_list = self._match_stdq_and_answers(
                        _question_vector, _milvus
                    )
                else:
                    # 只需查询一个问题分类的结果
                    _is_best, _match = self._match_stdq_and_answer_single(
                        _question_vector, _collection, _milvus, partition=_partition
                    )
                    if _match is None:
                        # 没有匹配到答案
                        _match_list = list()
                    else:
                        # 只返回第一个匹配上的
                        _match_list = [_match[0], ]

        # 对返回的标准问题和结果进行处理
        _answer = self._deal_with_match_list(
            question, session_id, _match_list, _collection, _context_id
        )

        # 返回答案
        return _answer

    #############################
    # 主动推送给客户端的消息处理
    #############################
    def add_send_message(self, user_id: int, msg, from_user_id: int = 0, from_user_name: str = '系统'):
        """
        向队列中添加待发送消息

        @param {int} user_id - 用户id
        @param {list|dict} msg - 要发送的消息内容
            [str, str, ...] - text类型消息，要发送的消息数组
            dict - json类型消息，要发送的json字典
        @param {int} from_user_id=0 - 来源用户id
        @param {int} from_user_name='系统' - 来源用户名
        """
        SendMessageQueue.create(
            from_user_id=from_user_id, from_user_name=from_user_name,
            user_id=user_id, msg_type='text' if type(msg) == list else 'json',
            msg=str(msg)
        )

    def query_send_message_count(self, user_id: int) -> int:
        """
        获取待发送消息数量

        @param {int} user_id - 用户id

        @returns {int} - 待发送消息数量
        """
        return SendMessageQueue.select().where(SendMessageQueue.user_id == user_id).count()

    def query_send_message(self, user_id: int) -> list:
        """
        获取待发送消息清单

        @param {int} user_id - 用户id

        @returns {list} - 获取到的消息清单队列
            [
                {
                    'from_user_id': x, 'from_user_name': '',
                    'msg_type': '', 'msg': object, 'create_time': ''
                }
            ]
        """
        _query = (SendMessageQueue.select().where(SendMessageQueue.user_id == user_id)
                  .order_by(SendMessageQueue.create_time.asc())
                  .limit(self.query_send_message_num))
        _msg_list = list()
        for _row in _query:
            _msg_list.append(
                {
                    'id': _row.id,
                    'from_user_id': _row.from_user_id,
                    'from_user_name': _row.from_user_name,
                    'msg_type': _row.msg_type,
                    'msg': eval(_row.msg),
                    'create_time': _row.create_time.strftime('%Y-%m-%d %H:%M:%S')
                }
            )

        # 返回结果
        return _msg_list

    def confirm_send_message(self, message_id: int):
        """
        确认已发送的消息id

        @param {int} message_id - 消息id
        """
        # 将数据迁移至历史表
        _message = SendMessageQueue.get_or_none(SendMessageQueue.id == message_id)
        if _message is not None:
            SendMessageHis.create(
                id=_message.id, from_user_id=_message.from_user_id,
                from_user_name=_message.from_user_name, user_id=_message.user_id,
                msg_type=_message.msg_type, msg=_message.msg,
                create_time=_message.create_time
            )

            SendMessageQueue.delete().where(SendMessageQueue.id == message_id).execute()

    #############################
    # 工具函数
    #############################

    def get_answer_by_std_question_id(self, std_question_id: int, session_id: str, context_id: str = None) -> list:
        """
        通过指定标准问题id获取答案

        @param {int} std_question_id - 标准问题id
        @param {str} session_id - 客户session id
        @param {str} context_id=None - 上下文临时id

        @returns {list} - 返回的问题答案字符数组，有可能是多个答案
        """
        _match_list = list()
        _stdq = StdQuestion.get_or_none(StdQuestion.id == std_question_id)
        if _stdq is not None:
            _answer = Answer.get(Answer.std_question_id == std_question_id)
            _match_list.append((_stdq, _answer))

        # 对返回的标准问题和结果进行预处理
        if len(_match_list) == 0:
            # 匹配不到问题的时候获取反馈信息
            _match_list = self._get_no_match_answer(session_id, None)
            if type(_match_list) == str:
                # 直接返回结果字符串
                return [_match_list]

        # 只匹配到1个答案
        _answer = self._get_match_one_answer(
            _stdq.question, session_id, _stdq.collection, _match_list, context_id=context_id
        )

        # 返回答案
        return _answer

    def answer_replace_pre_def(self, session_id: str, answers: list, replace_pre_def: bool = True,
                               context_id: str = None) -> list:
        """
        替换预定义的答案值

        @param {str} session_id - 客户session id
        @param {list} answers - 要处理的答案
        @param {bool} replace_pre_def=True - 是否进行替换
        @param {str} context_id=None - 上下文临时id

        @returns {list} - 处理后的答案
        """
        if not self.check_session_exists(session_id) or not replace_pre_def or type(answers[0]) != str:
            # 原样返回
            return answers

        # 替换函数
        def replace_var_fun(m):
            _match_str = m.group(0)
            _value = None
            if _match_str.startswith('{$info='):
                # 获取info的值
                _key = _match_str[7:-2]
                _session_value = self.get_info_by_key(session_id, _key, default=None)
                if _session_value is not None:
                    _value = _session_value
            elif _match_str.startswith('{$cache=') and context_id is not None:
                # 获取缓存的值
                _key = _match_str[8:-2]
                _value = self.get_cache_value(session_id, _key, default=None, context_id=context_id)
            elif _match_str.startswith('{$config='):
                # 获取qa_config的值
                _key = _match_str[9:-2]
                _value = self.qa_config.get(_key, None)
            elif _match_str.startswith('{$para='):
                # 通用参数
                _key = _match_str[7:-2]
                _value = self.qa_manager.DATA_MANAGER_PARA['common_para'].get(_key, None)

            if _value is not None:
                return str(_value)
            else:
                return _match_str

        # 逐行替换
        _len = len(answers)
        if _len > 0:
            if type(answers[0]) == dict:
                # 返回的是字典，变更字典值就可以
                for _key in answers[0].keys():
                    answers[0][_key] = re.sub(
                        r'\{\$.+?\$\}', replace_var_fun, answers[0][_key], re.M
                    )
            else:
                _index = 0
                while _index < _len:
                    answers[_index] = re.sub(
                        r'\{\$.+?\$\}', replace_var_fun, answers[_index], re.M
                    )
                    _index += 1

        # 返回结果
        return answers

    #############################
    # 内部函数
    #############################
    def _deal_with_match_list(self, question: str, session_id: str, match_list: list,
                              collection: str, context_id: str):
        """
        对标准问题和结果进行处理

        @param {str} question - 提出的问题
        @param {str} session_id=None - session id
        @param {list} match_list - 匹配到的问题答案数组[(StdQuestion, Answer), ]
        @param {str} collection - 问题分类
        @param {str} context_id - 上下文临时id

        @returns {list} - 返回答案数组
        """
        _match_list = match_list
        if len(_match_list) == 0:
            # 没有匹配到答案, 插入记录表用于后续改进
            NoMatchAnswers.create(
                session_info='' if not self.check_session_exists(session_id) else str(
                    self.get_info_dict(session_id)),
                question=question
            )
            # 匹配不到问题的时候获取反馈信息
            _match_list = self._get_no_match_answer(session_id, collection)
            if type(_match_list) == str:
                # 直接返回结果字符串
                return [_match_list]

        if len(_match_list) == 1:
            # 只匹配到1个答案
            _answer = self._get_match_one_answer(
                question, session_id, collection, _match_list, context_id
            )
        else:
            # 匹配到多个答案
            _answer = self._get_match_multiple_answer(
                question, session_id, collection, match_list
            )

        return _answer

    def _session_overtime_thread_fun(self, thread_id):
        """
        Session超时的出路线程

        @param {int} thread_id - 线程id
        """
        while not self._session_overtime_thread_stop:
            try:
                _del_list = list()
                if self.use_redis:
                    with redis.Redis(connection_pool=self.redis_pool) as _redis:
                        for _key in _redis.hkeys('chat_robot:session:list'):
                            _last_time = self._get_redis_dict_by_key(
                                'chat_robot:session:list', _key, _redis
                            )
                            if _last_time is None or type(_last_time) != datetime.datetime or (datetime.datetime.now() - _last_time).total_seconds() > self.session_overtime:
                                _del_list.append(_key)
                else:
                    for _key in self.sessions.keys():
                        if (datetime.datetime.now() - self.sessions[_key]['last_time']).total_seconds() > self.session_overtime:
                            _del_list.append(_key)

                # 开始清除
                for _session_id in _del_list:
                    self.delete_session(_session_id)

                self._log_debug('del overtime session: %s' % str(_del_list))
            except:
                self._log_debug('run exception: %s' % traceback.format_exc())

            # 等待
            time.sleep(self.session_checktime)

    def _pre_deal_context(self, question: str, session_id: str, collection: str, std_question_id: int,
                          std_question_tag: str):
        """
        上下文预处理

        @param {str} question - 提出的问题
        @param {str} session_id - session id
        @param {str} collection - 问题分类
        @param {int} std_question_id - 指定的标准问题id
        @param {str} std_question_tag - 指定的标准问题tag

        @returns {str, str, list, list, str} - 返回多元组 collection, partition, match_list, answers, context_id
            注：
            1、如果answers不为None，则直接返回该答案
            2、如果match_list不为None，则无需再匹配问题
        """
        # 基础准备
        _match_list = None
        _answers = None
        _context_id = None
        _collection = collection
        _partition = None

        # 特定处理的上下文id
        if session_id is not None:
            _context_dict = self.get_context_dict(session_id)
            if 'ask' in _context_dict.keys():
                _context_id = _context_dict['ask']['context_id']

        # 如果指定了标准问题，无需匹配，直接使用
        if std_question_id is not None:
            _match_list = [
                (StdQuestion.get(StdQuestion.id == std_question_id),
                 Answer.get(Answer.std_question_id == std_question_id))
            ]
            return _collection, _partition, _match_list, _answers, _context_id

        # 如果指定了标准问题tag
        if std_question_tag is not None:
            _std_q = StdQuestion.get(
                (StdQuestion.tag == std_question_tag) & (StdQuestion.collection == _collection)
            )
            _match_list = [
                (_std_q, Answer.get(Answer.std_question_id == _std_q.id))
            ]
            return _collection, _partition, _match_list, _answers, _context_id

        # 上下文预处理
        if session_id is not None:
            if 'options' in _context_dict.keys():
                # 选项处理
                if question.isdigit():
                    # 回答的内容是数字选项
                    _index = int(question)
                    _len = len(_context_dict['options']['options'])
                    if _index < 1 or _len < _index:
                        # 超过了选项值范围，重新提示, 修改提示内容即可
                        _answers = _context_dict['options']
                        _answers['tips'] = self.answer_replace_pre_def(
                            session_id, [self.select_options_out_index.replace(
                                '{$len$}', str(_len))],
                            replace_pre_def=True
                        )[0]

                        _answers = [_answers, ]
                    else:
                        _stdq_id = _context_dict['options']['options'][_index -
                                                                       1]['std_question_id']
                        _match_list = [
                            (StdQuestion.get(StdQuestion.id == _stdq_id),
                             Answer.get(Answer.std_question_id == _stdq_id))
                        ]
                        # 清除上下文
                        self.clear_session_dict(session_id, 'context')
                else:
                    # 非数字选项，按新问题处理，清除上下文
                    self.clear_session_dict(session_id, 'context')
            elif 'ask' in _context_dict.keys():
                # 提问处理
                _ask_info = _context_dict['ask']
                _context_id = _ask_info['context_id']
                _deal_fun = self.plugins['ask'][_ask_info['deal_class']][_ask_info['deal_fun']]
                _action, _ret = _deal_fun(
                    question, session_id, _context_id,
                    _ask_info['std_question_id'], _ask_info['collection'], _ask_info['partition'],
                    self, self.qa_manager, **_ask_info['param']
                )

                if _action is None:
                    _action = 'again'

                if _action == 'answer':
                    # 直接返回回复内容
                    _answers = self.answer_replace_pre_def(
                        session_id, _ret, _ask_info['replace_pre_def'],
                        context_id=_context_id
                    )
                    # 清除上下文
                    self.clear_session_dict(session_id, 'context')
                elif _action == 'to':
                    # 跳转到指定问题
                    _stdq_id = _ret
                    _match_list = [
                        (StdQuestion.get(StdQuestion.id == _stdq_id),
                            Answer.get(Answer.std_question_id == _stdq_id))
                    ]
                    # 清除上下文
                    self.clear_session_dict(session_id, 'context')
                elif _action == 'break':
                    # 跳出问题重新匹配问题，但可指定collection 和 partition
                    if _ret is not None:
                        if _ret[0] is not None:
                            _collection = _ret[0]

                        if _ret[1] is not None:
                            _partition = _ret[1]

                    # 清除上下文
                    self.clear_session_dict(session_id, 'context')
                else:
                    # 重新提问一次
                    if _ret is None:
                        _answers = [
                            Answer.get(Answer.std_question_id ==
                                       _ask_info['std_question_id']).answer
                        ]
                    else:
                        _answers = _ret

                    _answers = self.answer_replace_pre_def(
                        session_id, _answers, _ask_info['replace_pre_def'],
                        context_id=_context_id
                    )

        return _collection, _partition, _match_list, _answers, _context_id

    def _nlp_match_action(self, question: str, session_id: str, collection: str, partition: str):
        """
        使用NLP分词匹配问题意图

        @param {str} question - 提出的问题
        @param {str} session_id - session id
        @param {str} collection - 问题分类
        @param {str} partition - 问题场景

        @returns {str, str, list, str} - 返回多元组 collection, partition, match_list, answers
            注：
            1、如果answers不为None，则直接返回该答案
            2、如果match_list不为None，则无需再匹配问题
        """
        _answers = None
        _match_list = None
        _action_list = self.nlp.analyse_purpose(
            question, collection=collection, partition=partition, is_multiple=False
        )

        if len(_action_list) == 0:
            # 没有匹配到任何意图，直接返回
            return collection, partition, None, None

        # 匹配到意图，获取问题信息
        _collection = _action_list[0]['collection']
        _partition = _action_list[0]['partition']
        if _partition == '':
            _partition = None
        _stdq_id = _action_list[0]['std_question_id']
        _match_list = [
            (StdQuestion.get(StdQuestion.id == _stdq_id),
                Answer.get(Answer.std_question_id == _stdq_id))
        ]

        # 根据不同答案类型变更返回的列表信息, 将匹配信息更新至调用函数的参数中
        _answer = _match_list[0][1]
        if _answer.a_type in ('job', 'ask'):
            _matched_info = {
                'action': _action_list[0]['action'],
                'is_sure': _action_list[0]['is_sure'],
                'match_word': _action_list[0]['match_word'],
                'match_type': _action_list[0]['match_type'],
            }
            _matched_info.update(_action_list[0]['info'])
            _type_param = eval(_answer.type_param)
            if _answer.a_type == 'job':
                _type_param[2].update(_matched_info)
            elif _answer.a_type == 'ask':
                _type_param[4].update(_matched_info)

            _answer.type_param = str(_type_param)

        # 返回结果
        return _collection, _partition, _match_list, _answers

    def _match_stdq_and_answers(self, question_vector, milvus: mv.Milvus) -> list:
        """
        返回多个分类下匹配的问题答案清单

        @param {object} question_vector - 问题向量对象
        @param {mv.Milvus} milvus - Milvus服务器连接对象

        @returns {list} - 返回问题答案清单
        """
        _match_list = list()
        for _collection in self.qa_manager.sorted_collection:
            _is_best, _match = self._match_stdq_and_answer_single(
                question_vector, _collection, milvus
            )
            if _match is None:
                # 找不到结果的情况不处理
                continue

            if _is_best:
                # 是最优匹配，直接返回即可
                return _match

            # 添加到返回清单
            _match_list.extend(_match)

        # 返回匹配清单
        return _match_list

    def _match_stdq_and_answer_single(self, question_vector, collection: str, milvus: mv.Milvus,
                                      partition: str = None):
        """
        返回单个匹配的标准问题和答案

        @param {object} question_vector - 问题向量对象
        @param {str} collection - 问题分类
        @param {mv.Milvus} milvus - Milvus服务器连接对象
        @param {str} partition=None - 场景

        @returns {bool, list} - 返回是否最优匹配标志和问题答案 is_best, [(StdQuestion, Answer), ...], 如果查询不到返回None
            注意：有可能查到有StdQuestion，Answer为None的情况
        """
        _collection = collection
        if _collection is None:
            _collection = self.qa_manager.sorted_collection[0]

        _status, _result = milvus.search(
            _collection, top_k=self.multiple_in_collection, query_records=[question_vector, ],
            partition_tags=partition, params={'nprobe': self.nprobe}
        )
        self.qa_manager.confirm_milvus_status(_status, 'search')
        if len(_result) == 0:
            # 没有找到任何匹配项
            return False, None

        _match_list = list()
        _match_std = list()  # 匹配问题id清单，用于避免扩展问题重复匹配
        for _match in _result[0]:
            _stdq_and_answer = self._get_stdq_and_answer_from_db(
                _match.id, collection, partition
            )
            if _match.distance >= self.match_distance:
                # 最优匹配，直接返回
                return True, [_stdq_and_answer]
            elif _match.distance < self.multiple_distance:
                # 超过最小值，跳出循环
                break

            # 非最优匹配，加入到清单
            if _stdq_and_answer[0].id not in _match_std:
                _match_std.append(_stdq_and_answer[0].id)
                _match_list.append(_stdq_and_answer)

        # 进入到该步骤已是非最优匹配，检查匹配数量并返回
        if len(_match_list) > 0:
            return False, _match_list
        else:
            # 没有匹配到任何结果
            return False, None

    def _get_stdq_and_answer_from_db(self, milvus_id: int, collection: str, partition: str = None) -> tuple:
        """
        通过milvus_id查询标准问题答案

        @param {int} milvus_id - 要查询的milvus_id
        @param {str} collection - 问题分类
        @param {str} partition=None - 场景

        @returns {tuple} - 返回(StdQuestion, Answer), 如果查询不到返回None
            注意：有可能查到有StdQuestion，Answer为None的情况
        """
        _stdq = StdQuestion.get_or_none(
            (StdQuestion.milvus_id == milvus_id) & (StdQuestion.collection == collection) & (
                StdQuestion.partition == ('' if partition is None else partition))
        )
        if _stdq is None:
            # 查询问题扩展
            _sub_query = (ExtQuestion.select(ExtQuestion.std_question_id)
                          .where(ExtQuestion.milvus_id == milvus_id))
            _stdq = (StdQuestion.select()
                     .where(StdQuestion.id.in_(_sub_query) & (StdQuestion.collection == collection) & (
                         StdQuestion.partition == ('' if partition is None else partition)))
                     .get())
            if _stdq is None:
                # 扩展问题也找不到
                return None

        # 查询答案
        _answer = Answer.get(Answer.std_question_id == _stdq.id)

        # 返回结果
        return (_stdq, _answer)

    def _get_no_match_answer(self, session_id: str, collection: str):
        """
        在没有找到答案的情况下返回的值

        @param {str} session_id=None - session id
        @param {str} collection=None - 问题分类

        @returns {str|list} - 如果返回的是str，则代表直接回答该答案，否则返回的是[(StdQuestion, Answer)]
        """
        if self.no_answer_milvus_id == -1:
            # 直接返回server.xml设置的答案
            return self.no_answer_str

        # 从数据库中找标准问题和答案
        _collection = collection
        if collection is None:
            _collection = self.no_answer_collection
        _stdq = StdQuestion.get_or_none(
            (StdQuestion.milvus_id == self.no_answer_milvus_id) & (StdQuestion.collection == _collection) & (
                StdQuestion.partition == '')
        )
        if _stdq is None:
            _stdq = StdQuestion.get(
                (StdQuestion.milvus_id == self.no_answer_milvus_id) & (StdQuestion.collection == self.no_answer_collection) & (
                    StdQuestion.partition == '')
            )

        _answer = Answer.get_or_none((Answer.std_question_id == _stdq.id))

        return [(_stdq, _answer)]

    def _get_match_one_answer(self, question: str, session_id: str, collection: str, match_list: list,
                              context_id: str = None) -> str:
        """
        获取匹配到一个答案时的回复结果

        @param {str} question - 问题
        @param {str} session_id - 用户session id
        @param {str} collection - 问题分类
        @param {list} match_list - 匹配到的问题/答案列表
        @param {str} context_id=None - 上下文临时id

        @returns {list} - 返回的答案数组(只包含一个返回值)
        """
        _stdq = match_list[0][0]
        _answer = match_list[0][1]
        if _answer.a_type == 'text':
            # 直接返回文本
            return self.answer_replace_pre_def(
                session_id, [_answer.answer], _answer.replace_pre_def == 'Y', context_id=context_id
            )
        elif _answer.a_type == 'json':
            # json格式
            _json_dict = eval(self.answer_replace_pre_def(
                session_id, [_answer.answer], _answer.replace_pre_def == 'Y', context_id=context_id
            )[0])
            return [_json_dict]
        elif _answer.a_type == 'options':
            # 选项类答案处理，提示信息放在answer字段上, type_param的格式为：[[std_question_id, 'option_str'], ...]
            if not self.check_session_exists(session_id):
                raise FileNotFoundError('not support options if session id is None!')

            _options = eval(_answer.type_param)
            _back_answers = {
                'data_type': 'options',
                'tips': self.answer_replace_pre_def(
                    session_id, [_answer.answer, ], _answer.replace_pre_def == 'Y', context_id=context_id
                )[0],
                'options': list(),
            }

            _index = 1
            for _option in _options:
                _back_answers['options'].append({
                    'option_str': "%d. %s" % (_index, self.answer_replace_pre_def(
                        session_id, [_option[1], ], _answer.replace_pre_def == 'Y', context_id=context_id
                    )[0]),
                    'std_question_id': _option[0],
                    'index': _index
                })

                _index += 1

            # 添加到上下文
            self.add_options_context(session_id, _back_answers)

            return [_back_answers, ]
        elif _answer.a_type == 'job':
            # 操作类答案处理，如果处理完成为None，则用answer字段进行提示，type_param的格式为[class_name, fun_name, {para_dict}]
            _type_param = eval(_answer.type_param)
            _job_fun = self.plugins['job'][_type_param[0]][_type_param[1]]
            _action, _ret = _job_fun(
                question, session_id, match_list, self, self.qa_manager,
                **_type_param[2]
            )

            if _action == 'to':
                # 跳转到指定问题
                _stdq_id = _ret
                _job_match_list = [
                    (StdQuestion.get(StdQuestion.id == _stdq_id),
                        Answer.get(Answer.std_question_id == _stdq_id))
                ]

                return self._deal_with_match_list(
                    question, session_id, _job_match_list, [collection], context_id
                )
            else:
                # 直接返回回复内容
                _back_answers = _ret
                if _back_answers is None:
                    _back_answers = [_answer.answer]

                return self.answer_replace_pre_def(
                    session_id, _back_answers, _answer.replace_pre_def == 'Y', context_id=context_id
                )
        elif _answer.a_type == 'ask':
            # 提问类答案处理, 使用answer字段进行提问，type_param的格式为[class_name, fun_name, collection, partition, {para_dict}, True]
            _context_dict = self.get_context_dict(session_id)
            if 'ask' in _context_dict.keys() and _context_dict['ask']['std_question_id'] == _stdq.id:
                # 是自身并且问题ID一致，是延续性的处理
                _collection, _partition, _match_list, _answers, _context_id = self._pre_deal_context(
                    question, session_id, collection, None, None)

                if _answers is not None:
                    return _answers
                else:
                    # 继续处理
                    _answers = self._deal_with_match_list(
                        question, session_id, _match_list, _collection, _context_id
                    )
                    return _answers
            else:
                # 新的问题处理
                _type_param = eval(_answer.type_param)

                _ask_info = {
                    'deal_class': _type_param[0],
                    'deal_fun': _type_param[1],
                    'std_question_id': _stdq.id,
                    'collection': _type_param[2],
                    'partition': _type_param[3],
                    'param': _type_param[4],
                    'replace_pre_def': _answer.replace_pre_def == 'Y'
                }
                if context_id is not None:
                    _ask_info['context_id'] = context_id

                # 添加上下文
                self.add_ask_context(session_id, _ask_info)

                if len(_type_param) > 5 and _type_param[5]:
                    # 需要进行预处理
                    _collection, _partition, _match_list, _answers, _context_id = self._pre_deal_context(
                        question, session_id, collection, None, None)

                    if _answers is not None:
                        return _answers
                    else:
                        # 继续处理
                        _answers = self._deal_with_match_list(
                            question, session_id, _match_list, _collection, _context_id
                        )
                        return _answers
                else:
                    # 提示结果
                    return self.answer_replace_pre_def(
                        session_id, [_answer.answer], _answer.replace_pre_def == 'Y', context_id=context_id
                    )
        else:
            # 不支持的处理模式
            self._log_debug('not support answer type [%s]!' % _answer.a_type)

            # 视为没有找到问题
            _match_list = self._get_no_match_answer(session_id, collection)
            if type(_match_list) == str:
                return [_match_list]
            else:
                # 注意这里可能会因为no_answer的参数设置导致死循环，这个点一定要测试
                return self._get_match_one_answer(
                    question, session_id, collection, _match_list, context_id=None
                )

    def _get_match_multiple_answer(self, question: str, session_id: str, collection: str, match_list: list) -> str:
        """
        获取匹配到多个答案时的回复结果，组成返回清单

        @param {str} question - 问题
        @param {str} session_id - 用户session id
        @param {str} collection - 问题分类
        @param {list} match_list - 匹配到的问题/答案列表

        @returns {list} - 返回的提示问题结构数组: [dict, ], 字典定义如下：
            data_type = 'options' - 数据类型
            tips {str} - 开始提示信息
            options {list} - 选项清单，每个选项为一个字典
                option_str {str} - 选项显示文本
                std_question_id {int} - 选项对应标准问题id, 如果选项不是对应问题时送 -1
                index {int} - 选项对应顺序号
        """
        _answers = {
            'data_type': 'options',
            'options': list(),
        }
        _with_context = True  # 是否有上下文
        if not self.check_session_exists(session_id):
            # 无法使用session，改为提示问题的形式
            _answers['tips'] = self.select_options_tip_no_session
            _with_context = False
        else:
            # 准备选项上下文
            _answers['tips'] = self.select_options_tip

        # 组织选项
        _index = 1
        for _match in match_list:
            _answers['options'].append({
                'option_str': '%d. %s' % (_index, _match[0].question),
                'std_question_id': _match[0].id,
                'index': _index
            })

            _index += 1

        # 添加上下文
        if _with_context:
            self.add_options_context(session_id, _answers)

        # 返回结果
        return [_answers, ]

    #############################
    # Session相关的处理函数
    #############################
    def _check_redis_session_exists(self, session_id: str, redis_connection):
        """
        检查session是否存在

        @param {str} session_id - session id
        @param {object} redis_connection - redis的连接

        @returns {bool} - 是否存在
        """
        return redis_connection.hexists(
            'chat_robot:session:list',
            session_id
        )

    def _add_redis_dict(self, name: str, mapping: dict, redis_connection):
        """
        将字典存入redis中

        @param {str} name - redis中的访问key
        @param {dict} mapping - 要存入的字典
        @param {object} redis_connection - redis的连接
        """
        # 将字典转换为一维dict
        for _key in mapping:
            if type(mapping[_key]) == dict:
                # 如果是字典，继续调用自己进行下一级的处理
                _name = '%s:%s' % (name, _key)  # 下级对象的name是原来的基础上增加
                _mapping = mapping[_key]  # 缓存对象
                mapping[_key] = '%s:%s' % ('dict', _name)  # 指定当前对象类型为dict
                self._add_redis_dict(_name, _mapping, redis_connection)
            else:
                # 非字典，根据情况进行字符串的转换
                mapping[_key] = self._value_to_redis_str(mapping[_key])

        # 处理完成，存入redis
        if len(mapping) > 0:
            redis_connection.hset(name, mapping=mapping)

    def _add_redis_dict_value(self, name: str, key: str, value: object, redis_connection):
        """
        把指定值添加到redis字典中

        @param {str} name - redis的key
        @param {str} key - 字典中的搜索key
        @param {object} value - 值
        @param {object} redis_connection - Redis连接
        """
        if type(value) == dict:
            _name = '%s:%s' % (name, key)  # 下级对象的name是原来的基础上增加
            _mapping = copy.deepcopy(value)  # 缓存对象
            _value = '%s:%s' % ('dict', _name)  # 指定当前对象类型为dict

            # 添加下级字典
            self._add_redis_dict(_name, _mapping, redis_connection)
        else:
            _value = self._value_to_redis_str(value)

        # 处理完成，存入redis
        redis_connection.hset(name, key=key, value=_value)

    def _get_redis_dict(self, name: str, redis_connection) -> dict:
        """
        获取redis保存的dict

        @param {str} name - redis上的key
        @param {object} redis_connection - redis连接对象

        @returns {dict} - 返回的hash字典
        """
        _dict = redis_connection.hgetall(name)
        # 遍历每个值进行转换处理
        for _key in _dict.keys():
            _dict[_key] = self._redis_str_to_value(_dict[_key], redis_connection)

        return _dict

    def _get_redis_dict_by_key(self, name: str, key: str, redis_connection, default=None):
        """
        根据key获取字典值

        @param {str} name - redis的key
        @param {str} key - 字典中的搜索key
        @param {object} redis_connection - Redis连接
        @param {object} default=None - 取不到的默认值

        @returns {object} - 返回值
        """
        _value = redis_connection.hget(name, key)
        if _value is None:
            return default
        else:
            return self._redis_str_to_value(_value, redis_connection)

    def _clear_reids_dict(self, name: str, redis_connection):
        """
        清除指定的redis字典

        @param {str} name - redis上的key
        @param {object} redis_connection - redis连接对象
        """
        _dict = redis_connection.hgetall(name)
        for _key in _dict.keys():
            self._del_redis_dict_by_key(name, _key, redis_connection)

    def _del_redis_dict(self, name: str, redis_connection):
        """
        删除redis保存的字典
        注意：该函数只是删除字典本身，不会删除上一级字典的引用

        @param {str} name - redis上的key
        @param {object} redis_connection - redis连接对象
        """
        # 遍历检查是否有dict类型
        _dict = redis_connection.hgetall(name)
        for _key in _dict.keys():
            if _dict[_key].startswith('dict:'):
                # 删除子字典
                self._del_redis_dict(_dict[_key][5:], redis_connection)

        # 直接删除
        redis_connection.delete(name)

    def _del_redis_dict_by_key(self, name: str, key: str, redis_connection):
        """
        删除name字典下的key值

        @param {str} name - redis的字典key
        @param {str} key - 字典下的key索引
        @param {object} redis_connection - Redis连接
        """
        if redis_connection.hexists(name, key):
            # 删除下一级的字典(如果有的话)
            self._del_redis_dict('%s:%s' % (name, key), redis_connection)

            # 删除字典中的值
            redis_connection.hdel(name, key)

    def _value_to_redis_str(self, value: object) -> str:
        """
        将对象转换为redis格式字符串

        @param {object} value - 要转换的对象

        @returns {str} - 转换后的对象
        """
        _type = type(value)
        _str = ''
        if _type == str:
            _str = '%s:%s' % ('str', value)
        elif _type == int:
            _str = '%s:%s' % ('int', str(value))
        elif _type == float:
            _str = '%s:%s' % ('float', str(value))
        elif _type == bool:
            _str = '%s:%s' % ('bool', str(value))
        elif _type == datetime.datetime:
            _str = '%s:%s' % ('datetime', value.strftime('%Y-%m-%d %H:%M:%S'))
        else:
            # 其他类型，尝试转换为json
            _str = '%s:%s' % ('json', str(value))

        # 返回结果
        return _str

    def _redis_str_to_value(self, redis_str: str, redis_connection=None):
        """
        将redis获取到的对象转换为python对象

        @param {str} redis_str - redis存储的字符串
        @param {object} redis_connection=None - 到redis的连接对象，如果是dict对象要用到

        @returns {object} - python对象
        """
        try:
            # 获取信息
            _index = redis_str.find(':')
            if _index == -1:
                # 不符合格式要求原样返回
                return redis_str

            _type = redis_str[0: _index]
            _value_str = redis_str[_index + 1:]

            if _type == 'str':
                return _value_str
            elif _type == 'int':
                return int(_value_str)
            elif _type == 'float':
                return float(_value_str)
            elif _type == 'bool':
                return bool(_value_str)
            elif _type == 'datetime':
                return datetime.datetime.strptime(_value_str, '%Y-%m-%d %H:%M:%S')
            elif _type == 'json':
                return eval(_value_str)
            elif _type == 'dict':
                # 通过标识获取字典
                return self._get_redis_dict(_value_str, redis_connection)
            else:
                # 原样返回
                return redis_str
        except:
            # 异常原样返回
            self._log_error('Redis string [%s] to value error: %s' % (
                redis_str, traceback.format_exc()
            ))
            return redis_str

    #############################
    # 日志输出相关函数
    #############################

    def _log_info(self, msg: str, *args, **kwargs):
        """
        输出info日志

        @param {str} msg - 要输出的日志
        """
        if self.logger:
            if 'extra' not in kwargs:
                kwargs['extra'] = {'callFunLevel': 2}

            self.logger.info(msg, *args, **kwargs)

    def _log_debug(self, msg: str, *args, **kwargs):
        """
        输出debug日志

        @param {str} msg - 要输出的日志
        """
        if self.logger:
            if 'extra' not in kwargs:
                kwargs['extra'] = {'callFunLevel': 2}

            self.logger.debug(msg, *args, **kwargs)

    def _log_error(self, msg: str, *args, **kwargs):
        """
        输出error日志

        @param {str} msg - 要输出的日志
        """
        if self.logger:
            if 'extra' not in kwargs:
                kwargs['extra'] = {'callFunLevel': 2}

            self.logger.error(msg, *args, **kwargs)


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))

    _pool = redis.ConnectionPool(max_connections=100, host='10.16.85.63',
                                 port=6379, decode_responses=True)
    _r = redis.Redis(connection_pool=_pool)
    _keys = _r.keys('chat_robot:session:*')
    print(_keys)
