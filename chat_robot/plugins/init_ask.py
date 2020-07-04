#!/usr/bin/env python2
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
初始化的提问方式插件
@module init_ask
@file init_ask.py
"""

import os
import sys
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.qa import QA
from chat_robot.lib.data_manager import QAManager

__MOUDLE__ = 'init_ask'  # 模块名
__DESCRIPT__ = u'初始化的提问方式插件'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.06.29'  # 发布日期


class InitAsk(object):
    """
    默认初始化的提问函数
    """

    @classmethod
    def plugin_type(cls):
        """
        必须定义的函数，返回插件类型
        使用方法：
        1、每个函数的入参都是固定的，只是通过**kwargs传入答案中设置的个性参数；
        2、函数中可以自行处理具体的业务逻辑；
        3、函数的返回值是一个二元组：字符指示, 特定参数，外围将根据该返回值决定结束提问、跳转其他问题、重新提问
        """
        return 'ask'

    @classmethod
    def save_info(cls, question: str, session_id: str, context_id: str, std_question_id: int,
                  collection: str, partition: str,
                  qa: QA, qa_manager: QAManager, **kwargs):
        """
        直接保存信息至session的info中

        @param {str} question - 客户反馈的信息文本(提问回答)
        @param {str} session_id - 客户的session id
        @param {str} context_id - 上下文临时id
        @param {int} std_question_id - 上下文中对应的提问问题id
        @param {str} collection - 提问答案参数指定的问题分类
        @param {str} partition - 提问答案参数指定的场景标签
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 扩展传入参数
            info_key {str} - 从info字典中设置的key值
            to {int} - 处理完成后跳转到要处理的问题id，如果有该值则tips参数无效
            tips {str} - 处理完成的提示信息

        @returns {str, object} - 按照不同的处理要求返回内容
            'answer', [str, ...]  - 直接返回回复内容，第二个参数为回复内容
            'to', int - 跳转到指定问题处理，第二个参数为std_question_id
            'again', [str, ...] - 再获取一次答案，第二个参数为提示内容，如果第2个参数为None代表使用原来的参数再提问一次
            默认为'again'
        """
        _info_key = kwargs.get('info_key')
        _tips = kwargs.get('tips', 'save success!')
        _to = kwargs.get('to', None)
        _info = dict()
        _info[_info_key] = question
        qa.update_session_info(session_id, _info)
        if _to is None:
            return 'answer', [_tips, ]
        else:
            return 'to', _to

    @classmethod
    def multiple_save_info(cls, question: str, session_id: str, context_id: str, std_question_id: int,
                           collection: str, partition: str,
                           qa: QA, qa_manager: QAManager, **kwargs):
        """
        多轮问答保存信息至session的info中

        @param {str} question - 客户反馈的信息文本(提问回答)
        @param {str} session_id - 客户的session id
        @param {str} context_id - 上下文临时id
        @param {int} std_question_id - 上下文中对应的提问问题id
        @param {str} collection - 提问答案参数指定的问题分类
        @param {str} partition - 提问答案参数指定的场景标签
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 扩展传入参数
            ask {list} - 问题列表，注意最后的问题必须有tips或to参数
                [
                    {'info_key': '保存的key值', 'next_tips': '下一个问题'},
                    ...,
                    {'info_key': '保存的key值', 'tips': '处理完成提示', 'to': 跳转到指定问题id},
                ]
        @param {str, object} - 按照不同的处理要求返回内容
            'answer', [str, ...]  - 直接返回回复内容，第二个参数为回复内容
            'to', int - 跳转到指定问题处理，第二个参数为std_question_id
            'again', [str, ...] - 再获取一次答案，第二个参数为提示内容，如果第2个参数为None代表使用原来的参数再提问一次
            默认为'again'
        """
        _step = qa.get_cache_value(session_id, 'multiple_save_info', {}).get(context_id, 0)
        _ask = kwargs.get('ask')[_step]

        # 保存值
        _info_key = _ask.get('info_key')
        _info = dict()
        _info[_info_key] = question
        qa.update_session_info(session_id, _info)

        # 处理下一个问题
        _to = _ask.get('to', None)
        _tips = _ask.get('tips', None)
        _next_tips = _ask.get('next_tips', None)
        if _to is not None or _tips is not None:
            # 最后一个问题
            qa.del_cache(session_id, 'multiple_save_info')
            if _to is None:
                return 'answer', [_tips, ]
            else:
                return 'to', _to
        else:
            # 还有下一个问题
            qa.add_cache(session_id, 'multiple_save_info', {context_id: _step + 1})
            return 'again', [_next_tips, ]

    @classmethod
    def save_cache(cls, question: str, session_id: str, context_id: str, std_question_id: int,
                   collection: str, partition: str,
                   qa: QA, qa_manager: QAManager, **kwargs):
        """
        直接保存信息至session的cache中

        @param {str} question - 客户反馈的信息文本(提问回答)
        @param {str} session_id - 客户的session id
        @param {str} context_id - 上下文临时id
        @param {int} std_question_id - 上下文中对应的提问问题id
        @param {str} collection - 提问答案参数指定的问题分类
        @param {str} partition - 提问答案参数指定的场景标签
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 扩展传入参数
            info {dict} - 需要存入cache中的字典(按key存入)
            to {int} - 处理完成后跳转到要处理的问题id，如果有该值则tips参数无效
            tips {str} - 处理完成的提示信息

        @returns {str, object} - 按照不同的处理要求返回内容
            'answer', [str, ...]  - 直接返回回复内容，第二个参数为回复内容
            'to', int - 跳转到指定问题处理，第二个参数为std_question_id
            'again', [str, ...] - 再获取一次答案，第二个参数为提示内容，如果第2个参数为None代表使用原来的参数再提问一次
            默认为'again'
        """
        _info = kwargs.get('info', {})
        _tips = kwargs.get('tips', 'save cache success!')
        _to = kwargs.get('to', None)
        qa.update_cache_dict(session_id, _info, context_id=context_id)

        if _to is None:
            return 'answer', [_tips, ]
        else:
            return 'to', _to

    @classmethod
    def call_check_fun(cls, question: str, session_id: str, context_id: str, std_question_id: int,
                       collection: str, partition: str,
                       qa: QA, qa_manager: QAManager, **kwargs):
        """
        调用检查函数进行检查处理

        @param {str} question - 客户反馈的信息文本(提问回答)
        @param {str} session_id - 客户的session id
        @param {str} context_id - 上下文临时id
        @param {int} std_question_id - 上下文中对应的提问问题id
        @param {str} collection - 提问答案参数指定的问题分类
        @param {str} partition - 提问答案参数指定的场景标签
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 扩展传入参数
            fun {function} - 检查函数对象，格式为:
                fun(question, **kwargs):
                    retrun bool, [str, ...]  # 是否通过, 提示信息
            param {dict} - 调用检查函数的扩展参数

        @param {str, object} - 按照不同的处理要求返回内容
            'answer', [str, ...]  - 直接返回回复内容，第二个参数为回复内容
            'to', int - 跳转到指定问题处理，第二个参数为std_question_id
            'again', [str, ...] - 再获取一次答案，第二个参数为提示内容，如果第2个参数为None代表使用原来的参数再提问一次
            默认为'again'
        """
        _fun = kwargs.get('fun', None)
        _param = kwargs.get('param', {})

        if not callable(_fun):
            # 不可执行函数
            return 'answer', ['Sorry, error answer setting!']

        _param.update(
            {
                'session_id': session_id,
                'context_id': context_id,
                'std_question_id': std_question_id,
                'collection': collection,
                'partition': partition,
                'qa': qa,
                'qa_manager': qa_manager,
            }
        )

        _ok, _tips = _fun(question, **_param)

        if _ok:
            # 通过检查
            return 'answer', _tips
        else:
            # 需要重新提问
            return 'again', _tips


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))
