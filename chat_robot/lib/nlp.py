#!/usr/bin/env python2
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# 基于“结巴”中文分词：https://github.com/fxsjy/jieba
# 后续可能调整为HanLP：https://github.com/hankcs/HanLP


"""
语义解析(NLP)模块
@module nlp
@file nlp.py

词性编码	词性名称	注 解
Ag	形语素	形容词性语素。形容词代码为 a，语素代码ｇ前面置以A。
a	形容词	取英语形容词 adjective的第1个字母。
ad	副形词	直接作状语的形容词。形容词代码 a和副词代码d并在一起。
an	名形词	具有名词功能的形容词。形容词代码 a和名词代码n并在一起。
b	区别词	取汉字“别”的声母。
c	连词	取英语连词 conjunction的第1个字母。
dg	副语素	副词性语素。副词代码为 d，语素代码ｇ前面置以D。
d	副词	取 adverb的第2个字母，因其第1个字母已用于形容词。
e	叹词	取英语叹词 exclamation的第1个字母。
f	方位词	取汉字“方”。
g	语素	绝大多数语素都能作为合成词的“词根”，取汉字“根”的声母。
h	前接成分	取英语 head的第1个字母。
i	成语	取英语成语 idiom的第1个字母。
j	简称略语	取汉字“简”的声母。
k	后接成分。
l	习用语	习用语尚未成为成语，有点“临时性”，取“临”的声母。
m	数词	取英语 numeral的第3个字母，n，u已有他用。
Ng	名语素	名词性语素。名词代码为 n，语素代码ｇ前面置以N。
n	名词	取英语名词 noun的第1个字母。
nr	人名	名词代码 n和“人(ren)”的声母并在一起。
ns	地名	名词代码 n和处所词代码s并在一起。
nt	机构团体	“团”的声母为 t，名词代码n和t并在一起。
nz	其他专名	“专”的声母的第 1个字母为z，名词代码n和z并在一起。
o	拟声词	取英语拟声词 onomatopoeia的第1个字母。
p	介词	取英语介词 prepositional的第1个字母。
q	量词	取英语 quantity的第1个字母。
r	代词	取英语代词 pronoun的第2个字母,因p已用于介词。
s	处所词	取英语 space的第1个字母。
tg	时语素	时间词性语素。时间词代码为 t,在语素的代码g前面置以T。
t	时间词	取英语 time的第1个字母。
u	助词	取英语助词 auxiliary
vg	动语素	动词性语素。动词代码为 v。在语素的代码g前面置以V。
v	动词	取英语动词 verb的第一个字母。
vd	副动词	直接作状语的动词。动词和副词的代码并在一起。
vn	名动词	指具有名词功能的动词。动词和名词的代码并在一起。
w	标点符号
x	非语素字	非语素字只是一个符号，字母 x通常用于代表未知数、符号。
y	语气词	取汉字“语”的声母。
z	状态词	取汉字“状”的声母的前一个字母。
un	未知词	不可识别词及用户自定义词组。取英文Unkonwn首两个字母。
"""

import os
import sys
import re
import collections as cs
import jieba
import jieba.posseg as pseg
from HiveNetLib.base_tools.run_tool import RunTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))


__MOUDLE__ = 'nlp'  # 模块名
__DESCRIPT__ = u'语义解析(NLP)模块'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.06.30'  # 发布日期


class NLP(object):
    """
    自然语言语义解析工具类
    """

    def __init__(self, plugins: dict = {}, data_manager_para: dict = {}, set_dictionary: str = None,
                 user_dict: str = None, enable_paddle=False,
                 parallel_num: int = None, logger=None):
        """
        构造函数

        @param {dict} plugins={} - 插件字典，通过loader加载和传入
        @param {dict} data_manager_para={} - 通过QAManager加载的内存参数字典
        @param {str} set_dictionary=None - 设置默认词典，传入词典的地址，例如"data/dict.txt.big"
        @param {str} user_dict=None - 添加用户自定义词典，传入词典地址，例如"userdict.txt"
            词典格式为每行一个词，每一行分三部分：词语、词频（可省略）、词性（可省略），用空格隔开，顺序不可颠倒
            例如：
                创新办 3 i
                云计算 5
                凱特琳 nz
                台中
        @param {bool} enable_paddle=False - 是否使用paddle模式训练模型进行分词
        @param {int} parallel_num=None - 并行分词模式(多行的情况下并行处理，不支持Windows)
        @param {Logger} logger=None - 日志对象
        """
        self.logger = logger
        self.plugins = plugins
        self.DATA_MANAGER_PARA = data_manager_para

        if set_dictionary is not None:
            jieba.set_dictionary(set_dictionary)

        if user_dict is not None:
            jieba.load_userdict(user_dict)

        self.enable_paddle = enable_paddle
        self.parallel_num = parallel_num
        if parallel_num is not None:
            jieba.enable_parallel(parallel_num)

    #############################
    # 公共函数
    #############################

    def analyse_purpose(self, question: str, collections: list = None, partition: str = None, is_multiple: bool = False):
        """
        猜测问题意图

        @param {str} question - 问题句子
        @param {list} collection=None - 指定从特定的问题分类中分析
        @param {str} partition=None - 指定从特定的问题场景中分析
        @param {bool} is_multiple=False - 是否返回多个意图

        @return {list} - 匹配到的问题意图，如果返回的是[]代表没有匹配到意图
            [
                {
                    'action': '意图动作', 'collection': '意图所在分类', 'partition': '意图场景(可以为None)',
                    'is_sure': str_sure/negative/uncertain, 'order_num': int_优先顺序(降序),
                    'std_question_id': int_对应问题id, 'info': dict_意图特定信息
                },
                ...
            ]
        """
        _purpose = list()
        if len(question) == 0:
            # 空语句不处理
            return _purpose

        _amount_sign_list = eval(self.DATA_MANAGER_PARA.get('common_para', {})
                                 .get('amount_sign_list', "['$', '￥']"))
        _purpose_config_dict = self.DATA_MANAGER_PARA.get('nlp_purpos_config_dict', {})

        _words = pseg.cut(question, use_paddle=self.enable_paddle)
        _words_list = list()  # 完整的词典列表
        _s_start = 0  # 当前语句开始

        _matched_list = list()  # 匹配清单，用于控制不重复匹配
        _matched_in_s = list()  # 当前语句的匹配信息

        # 循环分析句子
        _word, _flag = _words.__next__()  # 当前词，作为开始
        _last_word, _last_flag = '', ''  # 上一词
        _next_word, _next_flag = '', ''  # 下一词
        _stop_iter = False  # 是否结束循环
        while True:
            # 获取下一个词
            try:
                if not _stop_iter:
                    _next_word, _next_flag = _words.__next__()
                else:
                    _next_word, _next_flag = '', ''
            except StopIteration:
                # 找不到, 打上退出循环的标记
                _stop_iter = True
                _next_word, _next_flag = '.', 'x'  # 增加一个句号，简化处理逻辑

            # 处理_words_list
            if _flag == 'm' and (_last_flag == 'm' or _last_word in _amount_sign_list):
                # 上一个字是币种标志, 或者上一个字是数量, 合并到上一个词中
                _word = _words_list[-1][0] + _word
                _words_list[-1][0] = _word
                _words_list[-1][1] = 'm'
            elif _word == ',' and _last_flag == 'm' and _next_flag == 'm':
                # m , m 的形式，统一合并到上一个词中
                _word = _last_word + _word + _next_word
                _flag = 'm'
                _words_list[-1][0] = _word
                _words_list[-1][1] = _flag
                # 由于已经使用了next，再获取一次next
                try:
                    if not _stop_iter:
                        _next_word, _next_flag = _words.__next__()
                    else:
                        _next_word, _next_flag = '', ''
                except StopIteration:
                    # 找不到, 打上退出循环的标记
                    _stop_iter = True
                    _next_word, _next_flag = '.', 'x'  # 增加一个句号，简化处理逻辑
            else:
                # 正常的新词, 添加到_words_list中
                _words_list.append([_word, _flag])

            # 匹配处理
            if (_flag == 'x' and _word != ' ') or _word in ('.'):
                for _action, _match_word, _collection, _partition in _matched_in_s:
                    # 处理意图列表
                    _config = _purpose_config_dict[_collection][_partition][_action]
                    _purpose.append(
                        {
                            'action': _action, 'collection': _collection, 'partition': _partition,
                            'match_word': _match_word,
                            'is_sure': self._judge_is_sure(_words_list[_s_start: len(_words_list)]),
                            'order_num': _config['order_num'],
                            'std_question_id': _config['std_question_id'],
                            'info': {},
                        }
                    )

                _s_start = len(_words_list)  # 指定下一句的开始位置
                _matched_in_s.clear()  # 清空当前语句的匹配数据
            else:
                # 使用词尝试匹配动作
                _action, _match_word, _collection, _partition = self._match_purpose(
                    _word, collections, partition)
                if _action != '':
                    # 匹配到动作
                    _match_str = '%s,%s,%s' % (_action, str(_collection), str(_partition))
                    if _match_str not in _matched_list:
                        _matched_list.append(_match_str)  # 登记避免重复
                        _matched_in_s.append([_action, _match_word, _collection, _partition])

            # 进入下一轮循环
            if _next_word == '':
                break
            else:
                _last_word, _last_flag = _word, _flag
                _word, _flag = _next_word, _next_flag
                continue

        # 重新排序
        _purpose = sorted(_purpose, key=lambda x: x['order_num'], reverse=True)

        # 进行意图的检查
        _matched_purpose = []
        for _pitem in _purpose:
            _config = _purpose_config_dict[_pitem['collection']
                                           ][_pitem['partition']][_pitem['action']]
            if len(_config['check']) > 0:
                # 需要进行检查
                _check_fun = self.plugins['nlpcheck'][_config['check'][0]][_config['check'][1]]
                if not _check_fun(
                    question, _words_list,
                    _pitem['action'], _pitem['match_word'], _pitem['collection'], _pitem['partition'],
                    _config['std_question_id'], **_config['check'][2]
                ):
                    # 检查未通过，继续检查下一个
                    continue
                else:
                    _matched_purpose.append(_pitem)
            else:
                # 没有配置检查函数，视为检查通过
                _matched_purpose.append(_pitem)

            # 看看是否需要处理下一个
            if not is_multiple and len(_matched_purpose) > 0:
                # 只匹配第一个即可
                break

        # 获取意图特定信息
        for _pitem in _matched_purpose:
            _config = _purpose_config_dict[_pitem['collection']
                                           ][_pitem['partition']][_pitem['action']]

            if len(_config['info']) > 0:
                _get_info_fun = self.plugins['nlpinfo'][_config['info'][0]][_config['info'][1]]
                _info_dict = _get_info_fun(
                    question, _words_list,
                    _pitem['action'], _pitem['match_word'], _pitem['collection'], _pitem['partition'],
                    _config['std_question_id'], **_config['info'][2]
                )
                _pitem['info'].update(_info_dict)

        self._log_debug('question: %s\n%s' % (question, str(_matched_purpose)))
        return _matched_purpose

    def cut_sentence(self, sentence: str, with_class: bool = True) -> list:
        """
        进行语句分词

        @param {str} sentence - 要分词的语句
        @param {bool} with_class=True - 是否包含词性信息

        @returns {list} - 获取到的分词列表
            如果with_class为False，返回的是词组列表，否则返回的是[(word, flag), ]的含词性的列表

        """
        _words = pseg.cut(sentence, use_paddle=self.enable_paddle)
        _words_list = list()  # 完整的词典列表
        for _word, _flag in _words:
            if with_class:
                _words_list.append((_word, _flag))
            else:
                _words_list.append(_word)

        return _words_list

    #############################
    # 内部函数
    #############################

    def _judge_is_sure(self, words: list):
        """
        判断一组词的词义是否肯定

        @param {list} words - 词数组[[word, flag], ...]

        @returns {str} - 'uncertain'-代表不确定，'sure'-肯定， 'negative'-否定
        """
        _sure_judge_dict = self.DATA_MANAGER_PARA.get('nlp_sure_judge_dict', {
            'sure': {}, 'negative': {}
        })
        _is_sure = None
        for _word, _flag in words:
            _temp_judge = None
            if _flag in _sure_judge_dict['negative'].keys() and _word in _sure_judge_dict['negative'][_flag]:
                _temp_judge = False
            elif _flag in _sure_judge_dict['sure'].keys() and _word in _sure_judge_dict['sure'][_flag]:
                _temp_judge = True

            # 组合判断肯定和否定
            if _is_sure is None:
                _is_sure = _temp_judge
            elif _temp_judge is not None:
                if _is_sure and not _temp_judge:
                    # 一肯定一否定
                    _is_sure = False
                elif not _is_sure and not _temp_judge:
                    # 两否定则为肯定，'不是不行'
                    _is_sure = True

        if _is_sure is not None:
            _is_sure = 'sure' if _is_sure else 'negative'
        else:
            _is_sure = 'uncertain'

        return _is_sure

    def _match_purpose(self, word: str, collections: list = None, partition: str = None):
        """
        按单词匹配意图动作

        @param {str} word - 要匹配的单词
        @param {list} collection=None - 指定从特定的问题分类中分析
        @param {str} partition=None - 指定从特定的问题场景中分析

        @returns {str,str, str,str} - action, word, collection, partition
        """
        # 简化逻辑处理
        _partition = partition
        if partition == '':
            _partition = None

        _collections = collections
        if _collections is None:
            _collections = [None, ]

        _purpose_config_dict = self.DATA_MANAGER_PARA.get('nlp_purpos_config_dict', {})

        # 遍历查找
        for _collection in _collections:
            _collection_dict = _purpose_config_dict.get(_collection, {})
            _partition_dict = _collection_dict.get(_partition, {})
            for _action in _partition_dict.keys():
                if word in _partition_dict[_action]['match_words']:
                    return _action, word, _collection, _partition

        # 没有找到
        return '', '', None, None

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

    # seg_list = jieba.cut("我来到北京清华大学", cut_all=False)
    # print("Default Mode: " + "/ ".join(seg_list))  # 精确模式
    # jieba.suggest_freq('寄快递', True)
    # words = pseg.cut("我要寄快递给广州的黎慧剑", use_paddle=True)  # jieba默认模式
    # words = pseg.cut("我要寄信给广州的黎慧剑", use_paddle=True)  # jieba默认模式
    words = pseg.cut("广州的天气", use_paddle=True)  # jieba默认模式
    for word, flag in words:
        print('%s %s' % (word, flag))

    # words = pseg.cut("我不是要转账")
    # # # words = pseg.cut("要怎么转账", use_paddle=True)  # jieba默认模式
    # for word, flag in words:
    #     print('%s %s' % (word, flag))
