#!/usr/bin/env python2
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
初始化的问题答案任务
@module init_job
@file init_job.py
"""

import os
import sys
import random
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.qa import QA
from chat_robot.lib.data_manager import QAManager


__MOUDLE__ = 'init_job'  # 模块名
__DESCRIPT__ = u'初始化的问题答案任务'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.06.29'  # 发布日期


class InitJob(object):
    """
    默认初始化的任务函数
    使用方法：
        1、每个函数的入参都是固定的，只是通过**kwargs传入答案中设置的个性参数；
        2、函数中可以自行处理具体的业务逻辑；
        3、函数的返回值是一个字符数组，为实际返回客户端的回答内容；
        4、如果返回None，则会自动获取触发job的答案的answer信息回答。
    """
    @classmethod
    def plugin_type(cls):
        """
        必须定义的函数，返回插件类型
        """
        return 'job'

    @classmethod
    def initialize(cls, loader, qa_manager, qa, **kwargs):
        """
        装载插件前执行的初始化处理
        可以不定义

        @param {QAServerLoader} loader - 服务装载器
        @param {QAManager} qa_manager - 数据管理
        @param {QA} qa - 问答服务
        """
        pass

    @classmethod
    def get_random_answer(cls, question: str, session_id: str, match_list: list,
                          qa: QA, qa_manager: QAManager, **kwargs) -> list:
        """
        返回随机答案

        @param {str} question - 原始问题
        @param {str} session_id - session_id
        @param {list} match_list - 匹配上的问题、答案对象: [(StdQuestion, Answer)]
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 扩展传入参数
            ids {list} - 随机标准问题id清单

        @returns {list} - 按照不同的处理要求返回内容
            'answer', [str, ...]  - 直接返回回复内容，第二个参数为回复内容
                注：如果第二个参数返回None代表使用传入的答案的answer字段作为提示
            'to', int - 跳转到指定问题处理，第二个参数为std_question_id
        """
        _ids = kwargs.get('ids', None)
        if _ids is None or len(_ids) == 0:
            # 直接返回当前答案的提示信息
            return 'answer', None

        # 随机选取问题答案
        _std_q_id = _ids[random.randint(0, len(_ids) - 1)]
        return 'to', _std_q_id

    @classmethod
    def get_random_answer_text(cls, question: str, session_id: str, match_list: list,
                               qa: QA, qa_manager: QAManager, **kwargs) -> list:
        """
        从答案文本数组中获取随机答案进行回答
        (answer字段为字符数组格式 "['a1', 'a2', ...]")

        @param {str} question - 原始问题
        @param {str} session_id - session_id
        @param {list} match_list - 匹配上的问题、答案对象: [(StdQuestion, Answer)]
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 扩展传入参数

        @returns {list} - 按照不同的处理要求返回内容
            'answer', [str, ...]  - 直接返回回复内容，第二个参数为回复内容
                注：如果第二个参数返回None代表使用传入的答案的answer字段作为提示
            'to', int - 跳转到指定问题处理，第二个参数为std_question_id
        """
        try:
            _answer_list = eval(match_list[0][1].answer)
        except:
            return 'answer', None

        # 随机选取问题答案
        _answer = _answer_list[random.randint(0, len(_answer_list) - 1)]
        return 'answer', [_answer, ]

    @classmethod
    def save_info_with_para(cls, question: str, session_id: str, match_list: list,
                            qa: QA, qa_manager: QAManager, **kwargs) -> list:
        """
        将传参的参数值保存到session的info字典中

        @param {str} question - 原始问题
        @param {str} session_id - session_id
        @param {list} match_list - 匹配上的问题、答案对象: [(StdQuestion, Answer)]
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 要保存的参数

        @returns {list} - 按照不同的处理要求返回内容
            'answer', [str, ...]  - 直接返回回复内容，第二个参数为回复内容
                注：如果第二个参数返回None代表使用传入的答案的answer字段作为提示
            'to', int - 跳转到指定问题处理，第二个参数为std_question_id
        """
        _info = dict()
        for _key in kwargs:
            if _key not in ('action', 'is_sure'):
                _info[_key] = kwargs[_key]

        qa.update_session_info(session_id, _info)

        # 直接返回当前答案的提示信息
        return 'answer', None


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))
