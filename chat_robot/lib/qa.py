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
import json
import datetime
import threading
import traceback
import inspect
import milvus as mv
import pandas as pd
from HiveNetLib.base_tools.file_tool import FileTool
from HiveNetLib.base_tools.import_tool import ImportTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.data_manager import QAManager, Answer, StdQuestion, ExtQuestion, NoMatchAnswers
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
                 qa_config: dict = {}, logger=None):
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

        # 插件plugins函数字典，格式为{'type':{'class_name': {'fun_name': fun, }, },}
        self.plugins = plugins

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
        self.sessions[_session_id] = {
            'last_time': datetime.datetime.now(),
            'info': copy.deepcopy(info),
            'context': dict(),
            'cache': dict(),
            'context_cache': dict(),
        }

        self._log_debug('generate session[%s]: %s' % (_session_id, str(self.sessions[_session_id])))
        return _session_id

    def update_session_info(self, session_id: str, info: dict):
        """
        更新session中的客户信息
        注意：更新操作只会变更key相同的信息，不删除原有key不相同的信息

        @param {str} session_id - session id
        @param {dict} info - 要更新的信息字典
        """
        if session_id not in self.sessions.keys():
            raise AttributeError('session_id [%s] not exists!')

        self.sessions[session_id]['info'].update(info)

        self._log_debug('update session[%s]: %s' % (session_id, str(self.sessions[session_id])))

    def delete_session(self, session_id: str):
        """
        清除指定的session

        @param {str} session_id - session id
        """
        _session = self.sessions.pop(session_id, None)

        self._log_debug('delete session[%s]: %s' % (session_id, str(_session)))

    #############################
    # 服务端上下文操作
    #############################
    def generate_context_id(self) -> str:
        """
        生成context_id

        @returns {str} - 返回一个新的context_id
        """
        return str(uuid.uuid1())

    def add_options_context(self, session_id: str, options: list):
        """
        增加选项上下文信息

        @param {str} session_id - 客户的session id
        @param {list} options - 选项列表，格式为:
            [
                [std_question_id, option_str],
                ...
            ]
        """
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
        self.sessions[session_id]['context'].clear()  # 清除所有上下文
        self.sessions[session_id]['context']['ask'] = ask_info
        self._log_debug('Session[%s] add ask context: %s' % (session_id, str(ask_info)))

    def add_cache(self, session_id: str, key: str, value, context_id: str = None):
        """
        添加缓存信息

        @param {str} session_id - 客户的session id
        @param {str} key - 缓存的key
        @param {object} value - 缓存的值
        @param {str} context_id=None - 指定的上下文id
        """
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

    def quession_search(self, question: str, session_id: str = None, collection: str = None) -> list:
        """
        搜寻问题答案并返回

        @param {str} question - 提出的问题
        @param {str} session_id=None - session id
        @param {str} collection=None - 问题分类

        @returns {list} - 返回的问题答案字符数组，有可能是多个答案
        """
        # 检查session是否存在
        if session_id is not None and session_id not in self.sessions.keys():
            raise FileNotFoundError('session id [%s] not exists!' % session_id)

        # 检查collection
        if collection is not None and collection not in self.answer_dao.sorted_collection:
            raise AttributeError('collection [%s] not exists!' % collection)

        # 根据上下文及传参， 设置collections、partition及
        _collections, _partition, _match_list, _answer, _context_id = self._pre_deal_context(
            question, session_id, collection
        )

        if _answer is not None:
            return _answer

        if _match_list is None and self.use_nlp:
            # 使用NLP语义解析尝试匹配意图
            _collections, _partition, _match_list, _answer = self._nlp_match_action(
                question, session_id, _collections, _partition
            )

        if _match_list is None:
            # 查询标准问题及答案
            with self.qa_manager.get_bert_client() as _bert, self.qa_manager.get_milvus() as _milvus:
                _vectors = _bert.encode([question, ])
                _question_vector = self.qa_manager.normaliz_vec(_vectors.tolist())[0]

                # 进行匹配
                if _partition is not None:
                    # 只需查询一个结果
                    _is_best, _match = self._match_stdq_and_answer_single(
                        _question_vector, _collections[0], _milvus, partition=_partition
                    )
                    if _match is None:
                        # 没有匹配到答案
                        _match_list = list()
                    else:
                        # 只返回第一个匹配上的
                        _match_list = [_match[0], ]
                else:
                    # 查询结果清单
                    _match_list = self._match_stdq_and_answers(
                        _question_vector, _collections, _milvus
                    )

        # 对返回的标准问题和结果进行处理
        _answer = self._deal_with_match_list(
            question, session_id, _match_list, _collections, _context_id
        )

        # 返回答案
        return _answer

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
        if not replace_pre_def or session_id is None or session_id not in self.sessions.keys():
            # 原样返回
            return answers

        # 替换函数
        def replace_var_fun(m):
            _match_str = m.group(0)
            if _match_str.startswith('{$info='):
                _key = _match_str[7:-2]
                if _key in self.sessions[session_id]['info'].keys():
                    return self.sessions[session_id]['info'][_key]
            elif _match_str.startswith('{$cache=') and context_id is not None:
                _key = _match_str[8:-2]
                _value = self.get_cache_value(session_id, _key, default=None, context_id=context_id)
                if _value is not None:
                    return _value

            return _match_str

        # 逐行替换
        _len = len(answers)
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
                              collections: list, context_id: str):
        """
        对标准问题和结果进行处理

        @param {str} question - 提出的问题
        @param {str} session_id=None - session id
        @param {list} match_list - 匹配到的问题答案数组[(StdQuestion, Answer), ]
        @param {list} collections - 问题分类数组
        @param {str} context_id - 上下文临时id

        @returns {list} - 返回答案数组
        """
        _match_list = match_list
        if len(_match_list) == 0:
            # 没有匹配到答案, 插入记录表用于后续改进
            NoMatchAnswers.create(
                session_info='' if session_id is None or session_id not in self.sessions.keys() else str(
                    self.sessions[session_id]['info']),
                question=question
            )
            # 匹配不到问题的时候获取反馈信息
            _match_list = self._get_no_match_answer(session_id, collections[0])
            if type(_match_list) == str:
                # 直接返回结果字符串
                return [_match_list]

        if len(_match_list) == 1:
            # 只匹配到1个答案
            _answer = self._get_match_one_answer(
                question, session_id, collections[0], _match_list, context_id
            )
        else:
            # 匹配到多个答案
            _answer = self._get_match_multiple_answer(
                question, session_id, collections[0], match_list
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

    def _pre_deal_context(self, question: str, session_id: str, collection: str):
        """
        上下文预处理

        @param {str} question - 提出的问题
        @param {str} session_id=None - session id
        @param {str} collection=None - 问题分类

        @returns {list, str, list, list, str} - 返回多元组 collections, partition, match_list, answers, context_id
            注：
            1、如果answers不为None，则直接返回该答案
            2、如果match_list不为None，则无需再匹配问题
        """
        # 基础准备
        _match_list = None
        _answers = None
        _context_id = None
        if collection is None:
            _collections = self.qa_manager.sorted_collection
        else:
            _collections = [collection, ]

        _partition = None

        # 上下文预处理
        if session_id is not None:
            _session = self.sessions[session_id]
            if 'options' in _session['context'].keys():
                # 选项处理
                if question.isdigit():
                    # 回答的内容是数字选项
                    _index = int(question)
                    _len = len(_session['context']['options'])
                    if _index < 1 or _len < _index:
                        # 超过了选项值范围，重新提示
                        _answers = self.answer_replace_pre_def(
                            session_id, [self.select_options_out_index.replace(
                                '{$len$}', str(_len))],
                            replace_pre_def=True
                        )

                        for _option in _session['context']['options']:
                            _answers.append(_option[1])
                    else:
                        _stdq_id = _session['context']['options'][_index - 1][0]
                        _match_list = [
                            (StdQuestion.get(StdQuestion.id == _stdq_id),
                             Answer.get(Answer.std_question_id == _stdq_id))
                        ]
                        # 清除上下文
                        _session['context'].pop('options')
                else:
                    # 非数字选项，按新问题处理，清除上下文
                    _session['context'].pop('options')
            elif 'ask' in _session['context'].keys():
                # 提问处理
                _ask_info = _session['context']['ask']
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
                    _session['context'].clear()
                elif _action == 'to':
                    # 跳转到指定问题
                    _stdq_id = _ret
                    _match_list = [
                        (StdQuestion.get(StdQuestion.id == _stdq_id),
                            Answer.get(Answer.std_question_id == _stdq_id))
                    ]
                    # 清除上下文
                    _session['context'].clear()
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

        return _collections, _partition, _match_list, _answers, _context_id

    def _nlp_match_action(self, question: str, session_id: str, collections: list, partition: str):
        """
        使用NLP分词匹配问题意图

        @param {str} question - 提出的问题
        @param {str} session_id - session id
        @param {list} collections - 问题分类数组
        @param {str} partition - 问题场景

        @returns {list, str, list, str} - 返回多元组 collections, partition, match_list, answers
            注：
            1、如果answers不为None，则直接返回该答案
            2、如果match_list不为None，则无需再匹配问题
        """
        _answers = None
        _match_list = None
        _action_list = self.nlp.analyse_purpose(
            question, collections=collections, partition=partition, is_multiple=False
        )

        if len(_action_list) == 0:
            # 没有匹配到任何意图，直接返回
            return collections, partition, None, None

        # 匹配到意图，获取问题信息
        _collections = [_action_list[0]['collection']]
        _partition = [_action_list[0]['partition']]
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
                'is_sure': _action_list[0]['is_sure']
            }
            _matched_info.update(_action_list[0]['info'])
            _type_param = eval(_answer.type_param)
            if _answer.a_type == 'job':
                _type_param[2].update(_matched_info)
            elif _answer.a_type == 'ask':
                _type_param[4].update(_matched_info)
                # 需要执行后面的流程将问题

            _answer.type_param = json.dumps(_type_param, ensure_ascii=False)

        # 返回结果
        return _collections, _partition, _match_list, _answers

    def _match_stdq_and_answers(self, question_vector, collections: list, milvus: mv.Milvus) -> list:
        """
        返回多个分类下匹配的问题答案清单

        @param {object} question_vector - 问题向量对象
        @param {list} collections - 问题分类清单(按顺序排序)
        @param {mv.Milvus} milvus - Milvus服务器连接对象

        @returns {list} - 返回问题答案清单
        """
        _match_list = list()
        for _collection in collections:
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
        _status, _result = milvus.search(
            collection, top_k=self.multiple_in_collection, query_records=[question_vector, ],
            partition_tags=partition, params={'nprobe': self.nprobe}
        )
        self.qa_manager.confirm_milvus_status(_status, 'search')
        if len(_result) == 0:
            # 没有找到任何匹配项
            return False, None

        _match_list = list()
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
        elif _answer.a_type == 'options':
            # 选项类答案处理，提示信息放在answer字段上, type_param的格式为：[[std_question_id, 'option_str'], ...]
            if session_id is None or session_id not in self.sessions.keys():
                raise FileNotFoundError('not support options if session id is None!')

            _options = eval(_answer.type_param)
            _back_answers = [_answer.answer]
            _index = 1
            for _option in _options:
                _back_answers.append("%d. %s" % (_index, _option[1]))
                _index += 1

            # 添加到上下文
            self.add_options_context(session_id, _options)

            return self.answer_replace_pre_def(
                session_id, _back_answers, _answer.replace_pre_def == 'Y', context_id=context_id
            )
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
            # 提问类答案处理, 使用answer字段进行提问，type_param的格式为[class_name, fun_name, collection, partition, {para_dict}]
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

            if len(_type_param) > 5 and _type_param[5] == 'true':
                # 需要进行预处理
                _collections, _partition, _match_list, _answers, _context_id = self._pre_deal_context(
                    question, session_id, collection)

                if _answers is not None:
                    return _answers
                else:
                    # 继续处理
                    _answers = self._deal_with_match_list(
                        question, session_id, _match_list, _collections, _context_id
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

        @returns {list} - 返回的提示问题清单
        """
        _answers = list()
        if session_id is None or session_id not in self.sessions.keys():
            # 无法使用session，改为提示问题的形式
            _answers.append(self.select_options_tip_no_session)
            _options = None
        else:
            # 准备选项上下文
            _answers.append(self.select_options_tip)
            _options = list()

        # 组织选项
        _index = 1
        for _match in match_list:
            _option_str = '%d. %s' % (_index, _match[0].question)
            _answers.append(_option_str)
            if _options is not None:
                _options.append(
                    [_match[0].id, _option_str]
                )

            _index += 1

        # 添加上下文
        if _options is not None:
            self.add_options_context(session_id, _options)

        # 返回结果
        return _answers

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
