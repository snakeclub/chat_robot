#!/usr/bin/env python2
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
初始化的意图检查函数
@module init_nlpcheck
@file init_nlpcheck.py
"""

import os
import sys
import re
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.qa import QA
from chat_robot.lib.data_manager import QAManager


__MOUDLE__ = 'init_nlpcheck'  # 模块名
__DESCRIPT__ = u'初始化的意图检查函数'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.07.02'  # 发布日期


class InitCheck(object):
    """
    初始化的意图检查函数
    """
    @classmethod
    def plugin_type(cls):
        """
        必须定义的函数，返回插件类型
        """
        return 'nlpcheck'

    @classmethod
    def check_by_nest(cls, question: str, words: list, action: str, match_word: str, collection: str,
                      partition: str, std_question_id: int, **kwargs):
        """
        根据紧靠匹配动作词的词组否决意图

        @param {str} question - 完整的问题句子
        @param {list} words - 分词列表
        @param {str} action - 匹配上的意图
        @param {str} match_word - 匹配上的词
        @param {str} collection - 意图所属问题分类
        @param {str} partition - 意图所属场景
        @param {int} std_question_id - 对应标准问题id
        @param {kwargs} - 扩展信息，来源于nlp_purpos_config_dict配置的入参参数
            next {dict} - 紧接匹配词的后续词组配置，key为匹配词，value为紧接词组列表
            prev {dict} - 紧接意图词的前缀词组配置，key为匹配词，value为紧接词组列表

        @returns {bool} - 是否通过检查
        """
        _next = kwargs.get('next', {})
        _prev = kwargs.get('prev', {})
        _index = 0
        _len = len(words)
        for _word, _flag in words:
            if _word == match_word:
                # 匹配到匹配词组
                if _index < _len - 1 and _word in _next.keys() and words[_index + 1][0] in _next[_word]:
                    # 匹配到紧接词
                    return False

                if _index > 0 and _word in _prev.keys() and words[_index - 1][0] in _prev[_word]:
                    # 匹配到前缀
                    return False

                _index += 1

        # 检查通过
        return True


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))
