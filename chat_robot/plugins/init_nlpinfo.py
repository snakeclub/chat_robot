#!/usr/bin/env python2
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
初始化的意图信息获取函数
@module init_nlpinfo
@file init_nlpinfo.py
"""

import os
import sys
import re
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.qa import QA
from chat_robot.lib.data_manager import QAManager


__MOUDLE__ = 'init_nlpinfo'  # 模块名
__DESCRIPT__ = u'初始化的意图信息获取函数'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.07.02'  # 发布日期


class InitInfo(object):
    """
    初始化的意图信息获取函数
    """
    @classmethod
    def plugin_type(cls):
        """
        必须定义的函数，返回插件类型
        """
        return 'nlpinfo'

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
    def get_by_question(cls, question: str, words: list, action: str, match_word: str, match_type: str,
                        collection: str, partition: str, std_question_id: int, **kwargs):
        """
        通用根据问题本身信息函数

        @param {str} question - 完整的问题句子
        @param {list} words - 分词列表
        @param {str} action - 匹配上的意图
        @param {str} match_word - 匹配上的词
        @param {str} match_type - 匹配类型，exact_match-精确匹配，nlp_match-分词匹配
        @param {str} collection - 意图所属问题分类
        @param {str} partition - 意图所属场景
        @param {int} std_question_id - 对应标准问题id
        @param {kwargs} - 扩展信息，来源于nlp_purpos_config_dict配置的入参参数
            'condition' {list} - 匹配清单，数组每个为一个匹配对象配置字典:
                {
                    'key': str_匹配后的key值,
                    're_find': list_按正则表达式从词中获取内容(re.findall, 取第一个匹配值，非空)
                }

        @returns {dict} - 返回匹配到的info列表字典，传出的值将放入job及ask执行函数的kwargs参数中
        """
        _info = dict()
        for _condition in kwargs.get('condition', '[]'):
            # 要匹配的key
            _key = _condition.get('key', '')
            if _key == '':
                # key是必须的值
                continue
            del _condition['key']
            if _key in _info.keys():
                # 已存在，不覆盖
                continue

            # 进行信息抽取
            _re_find = _condition.get('re_find', None)
            if _re_find is None:
                continue

            if _re_find[1] is None:
                _match_list = re.findall(_re_find[0], question)
            else:
                _match_list = re.findall(_re_find[0], question, _re_find[1])

            if len(_match_list) > 0:
                _info[_key] = _match_list[0]

        # 返回结果
        return _info

    @classmethod
    def get_by_words(cls, question: str, words: list, action: str, match_word: str, match_type: str,
                     collection: str, partition: str, std_question_id: int, **kwargs):
        """
        通用获取词信息函数

        @param {str} question - 完整的问题句子
        @param {list} words - 分词列表
        @param {str} action - 匹配上的意图
        @param {str} match_word - 匹配上的词
        @param {str} match_type - 匹配类型，exact_match-精确匹配，nlp_match-分词匹配
        @param {str} collection - 意图所属问题分类
        @param {str} partition - 意图所属场景
        @param {int} std_question_id - 对应标准问题id
        @param {kwargs} - 扩展信息，来源于nlp_purpos_config_dict配置的入参参数
            'condition' {list} - 匹配清单，数组每个为一个匹配对象配置字典:
                {
                    'key': str_匹配后的key值,
                    'class': list_要匹配的词的词性列表-可选,
                    're_find': list_按正则表达式从词中获取内容(re.findall, 取第一个匹配值，非空)-可选,
                        [str_表达式, int_flags(不传则送None)]
                    're_match': list_按正则表达式判断词是否满足匹配内容(不修改，只判断是否包含)-可选，
                        [str_表达式, int_flags(不传则送None)]
                    'len_min': int_词最小长度-可选,
                    'len_max': int_词最大长度-可选,
                }

        @returns {dict} - 返回匹配到的info列表字典，传出的值将放入job及ask执行函数的kwargs参数中
        """
        _info = dict()
        # 遍历获取信息
        for _word in words:
            for _condition in kwargs.get('condition', '[]'):
                # 要匹配的key
                _key = _condition.get('key', '')
                if _key == '':
                    # key是必须的值
                    continue
                if _key in _info.keys():
                    # 已存在，不覆盖
                    continue

                # 遍历条件
                _is_match = True
                _match_word = _word[0]
                for _judge in _condition.keys():
                    if _judge == 'key':
                        continue

                    if _judge == 'class' and _word[1] not in _condition[_judge]:
                        _is_match = False
                        break

                    if _judge == 're_find':
                        if _condition[_judge][1] is None:
                            _match_list = re.findall(_condition[_judge][0], _match_word)
                        else:
                            _match_list = re.findall(
                                _condition[_judge][0], _match_word, _condition[_judge][1])

                        if len(_match_list) == 0:
                            _is_match = False
                            break
                        else:
                            # 修改_word的值
                            _match_word = _match_list[0]

                    if _judge == 're_match':
                        if _condition[_judge][1] is None:
                            _match_list = re.search(_condition[_judge][0], _match_word)
                        else:
                            _match_list = re.search(
                                _condition[_judge][0], _match_word, _condition[_judge][1])

                        if not _match_list:
                            _is_match = False
                            break

                    if _judge == 'len_min' and len(_match_word) < _condition[_judge]:
                        _is_match = False
                        break
                    elif _judge == 'len_max' and len(_match_word) > _condition[_judge]:
                        _is_match = False
                        break

                if _is_match:
                    _info[_key] = _match_word

        # 返回信息
        return _info

    @classmethod
    def get_wordclass_list(cls, question: str, words: list, action: str, match_word: str, match_type: str,
                           collection: str, partition: str, std_question_id: int, **kwargs):
        """
        获取词性对应的词列表

        @param {str} question - 完整的问题句子
        @param {list} words - 分词列表
        @param {str} action - 匹配上的意图
        @param {str} match_word - 匹配上的词
        @param {str} match_type - 匹配类型，exact_match-精确匹配，nlp_match-分词匹配
        @param {str} collection - 意图所属问题分类
        @param {str} partition - 意图所属场景
        @param {int} std_question_id - 对应标准问题id
        @param {kwargs} - 扩展信息，来源于nlp_purpos_config_dict配置的入参参数
            'condition' {list} - 匹配清单，数组每个为一个匹配对象配置字典:
                {
                    'key': str_匹配后的key值,
                    'class': list_要匹配的词性列表,
                }

        @returns {dict} - 返回匹配到的info列表字典，传出的值将放入job及ask执行函数的kwargs参数中
        """
        _info = dict()
        # 遍历获取信息
        for _word in words:
            for _condition in kwargs.get('condition', '[]'):
                # 要匹配的key
                _key = _condition.get('key', '')
                if _key == '':
                    # key是必须的值
                    continue

                if _key not in _info.keys():
                    _info[_key] = list()

                # 匹配词性
                if _word[1] in _condition.get('class', []):
                    _info[_key].append(_word[0])

        # 返回结果
        return _info


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))
