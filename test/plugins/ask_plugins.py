#!/usr/bin/env python2
# -*- coding: UTF-8 -*-

import os
import sys
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.qa import QA
from chat_robot.lib.data_manager import QAManager


class TestAskPlugins(object):
    """
    默认初始化的提问函数
    """

    @classmethod
    def plugin_type(cls):
        """
        必须定义的函数，返回插件类型
        """
        return 'ask'

    @classmethod
    def test_pay_fun(cls, question: str, session_id: str, context_id: str, std_question_id: int,
                     collection: str, partition: str,
                     qa: QA, qa_manager: QAManager, **kwargs):
        """
        多轮转账的示例

        @param {str} question - 客户反馈的信息文本(提问回答)
        @param {str} session_id - 客户的session id
        @param {str} context_id - 上下文临时id
        @param {int} std_question_id - 上下文中对应的提问问题id
        @param {str} collection - 提问答案参数指定的问题分类
        @param {str} partition - 提问答案参数指定的场景标签
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 扩展传入参数

        @returns {str, object} - 按照不同的处理要求返回内容
            'answer', [str, ...]  - 直接返回回复内容，第二个参数为回复内容
            'to', int - 跳转到指定问题处理，第二个参数为std_question_id
            'again', [str, ...] - 再获取一次答案，第二个参数为提示内容，如果第2个参数为None代表使用原来的参数再提问一次
            默认为'again'
        """
        _cache = qa.get_cache_dict(session_id, default={}, context_id=context_id)

        # 存入转账信息
        if 'step' not in _cache.keys():
            # 通过nlp意图发起的处理
            qa.update_cache_dict(session_id, kwargs, context_id=context_id)
            _cache = qa.get_cache_dict(session_id, default={}, context_id=context_id)
        elif _cache['step'] == 'in_name':
            _cache['in_name'] = question
            qa.add_cache(session_id, 'in_name', question, context_id=context_id)
        elif _cache['step'] == 'amount':
            _cache['amount'] = question
            qa.add_cache(session_id, 'amount', question, context_id=context_id)
        elif _cache['step'] == 'confirm':
            if question == '是的':
                return 'answer', ['执行向 {$cache=in_name$} 转账 {$cache=amount$}']
            else:
                return 'answer', ['取消转账操作']

        # 判断要问的问题
        if 'in_name' not in _cache.keys():
            qa.add_cache(session_id, 'step', 'in_name', context_id=context_id)
            return 'again', ['请输入收款人名称']
        elif 'amount' not in _cache.keys():
            qa.add_cache(session_id, 'step', 'amount', context_id=context_id)
            return 'again', ['请输入转账金额']
        else:
            # 最后一次确认
            qa.add_cache(session_id, 'step', 'confirm', context_id=context_id)
            return 'again', ['您确定要向 {$cache=in_name$} 转账 {$cache=amount$} 吗？输入 是的 执行转账操作，输入其他将取消操作']


class TestPlugins(object):
    """
    默认初始化的提问函数
    """

    @classmethod
    def plugin_type(cls):
        """
        必须定义的函数，返回插件类型
        """
        return 'test'

    @classmethod
    def test_call_check_fun(cls, question: str, **kwargs):
        """
        测试call_check_fun的处理

        @param {str} question - <description>
        """
        if question == '1':
            return True, ['结束提问']
        else:
            return False, None
