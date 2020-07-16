#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
API工具扩展插件模块
@module api_tools
@file api_tools.py
"""

import os
import sys
import json
import datetime
import copy
import redis
from HiveNetLib.base_tools.net_tool import NetTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.qa import QA
from chat_robot.lib.data_manager import QAManager
from chat_robot.lib.answer_db import StdQuestion, Answer, NlpPurposConfigDict


__MOUDLE__ = 'api_tools'  # 模块名
__DESCRIPT__ = u'API工具扩展插件模块'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.07.07'  # 发布日期


CITY_DATA_PATH = './api_tools'  # 城市数据文件路径，注意如果是相对路径，是以插件文件所在路径开始
CITY_DATA_FILENAME = 'city_data.json'  # 城市数据文件名
CITY_DATA_FORCE_UPDATE = False  # 指定强制更新数据

WEATHER_TRY_USE_IP_ADDR = True  # 如果没有客户地址信息，尝试通过IP地址获取
WEATHER_COLLECTION = 'test_chat'  # 天气问题的分类集, 需注意修改
WEATHER_PARTITION = ''  # 天气问题的特殊场景
WEATHER_ERROR = u'亲, 没有找到您需要的天气信息'  # 没有找到天气信息返回的回答


class ApiToolAsk(object):
    """
    ask模式的Api工具
    """
    @classmethod
    def plugin_type(cls):
        """
        必须定义的函数，返回插件类型
        """
        return 'ask'

    @classmethod
    def initialize(cls, loader, qa_manager: QAManager, qa: QA, **kwargs):
        """
        装载插件前执行的初始化处理

        @param {QAServerLoader} loader - 服务装载器
        @param {QAManager} qa_manager - 数据管理
        @param {QA} qa - 问答服务
        """
        # 将城市数据导入Redis
        cls._load_city_data(loader, qa_manager, qa, **kwargs)

        # 装载天气问答的数据库配置
        cls._add_weather_db_config(loader)

    @classmethod
    def weather(cls, question: str, session_id: str, context_id: str, std_question_id: int,
                collection: str, partition: str,
                qa: QA, qa_manager: QAManager, **kwargs):
        """
        查询天气

        @param {str} question - 客户反馈的信息文本(提问回答)
        @param {str} session_id - 客户的session id
        @param {str} context_id - 上下文临时id
        @param {int} std_question_id - 上下文中对应的提问问题id
        @param {str} collection - 提问答案参数指定的问题分类
        @param {str} partition - 提问答案参数指定的场景标签
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 扩展传入参数
            time {list} - nlp分词的时间词语列表
            addr {list} - nlp分词的地址词语列表

        @returns {str, object} - 按照不同的处理要求返回内容
            'answer', [str, ...]  - 直接返回回复内容，第二个参数为回复内容
            'to', int - 跳转到指定问题处理，第二个参数为std_question_id
            'again', [str, ...] - 再获取一次答案，第二个参数为提示内容，如果第2个参数为None代表使用原来的参数再提问一次
            'break', [collection, partition] - 跳出问题(让问题继续走匹配流程)，可以返回[collection, partition]变更分类和场景
            默认为'again'
        """
        _match_city_code = ''
        _match_day = 0  # 0代表当前，1代表明天，2代表后天
        # 检查是不是第二次的选项
        _cache_info = qa.get_cache_value(session_id, 'weather', default=None, context_id=context_id)
        if _cache_info is not None:
            if question.isdigit():
                if question not in _cache_info['addr_dict'].keys():
                    # 回答不在选项范围
                    return 'again', ['亲, 您输入的序号不对, 请输入正确的序号选择城市', ]
                else:
                    _match_day = _cache_info['day']
                    _match_city_code = _cache_info['addr_dict'][question]
            else:
                # 不是选项，是文字
                return 'answer', [WEATHER_ERROR, ]
        else:
            # 尝试获取日期
            for _word in kwargs.get('time', []):
                if _word in ['明天']:
                    _match_day = 1
                elif _word in ['后天']:
                    _match_day = 2

            # 尝试获取地址
            with redis.Redis(connection_pool=qa.redis_pool) as _redis:
                _match_addr = cls._search_city(kwargs.get('addr', []), _redis)
                if len(_match_addr) == 0:
                    # 没有匹配到地址，尝试获取客户info中的地址
                    _addr = qa.get_info_by_key(session_id, 'addr', default='')

                    if _addr == '' and WEATHER_TRY_USE_IP_ADDR:
                        # 尝试通过IP地址获取地址
                        _addr = cls._get_addr_by_ip(
                            qa.get_info_by_key(session_id, 'ip', default=''), qa
                        )

                    if _addr != '':
                        _addrs_with_class = qa.nlp.cut_sentence(_addr)
                        _addrs = [item[0] for item in _addrs_with_class]
                        _match_addr = cls._search_city(
                            _addrs, _redis
                        )

                _len = len(_match_addr)
                if _len == 1:
                    _match_city_code = _match_addr[0][1][0]
                elif _len > 1:
                    # 匹配到多个，进行提问让客户选择
                    _tips = ['找到了多个地址，您想查询哪个地址的天气？请输入序号进行选择: ']
                    _index = 1
                    _cache_info = dict()
                    _cache_info['day'] = _match_day
                    _cache_info['addr_dict'] = dict()
                    for item in _match_addr:
                        # 加入到上下文
                        _cache_info['addr_dict'][str(_index)] = item[1][0]

                        # 获取详细地址
                        _tips.append('%d.%s' % (_index, cls._get_city_full_name(item[0], _redis)))
                        _index += 1

                    # 添加到cache中
                    qa.add_cache(session_id, 'weather', _cache_info, context_id=context_id)

                    # 重新提问
                    return 'again', _tips

        if _match_city_code == '':
            # 没有找到地址，直接返回退出
            return 'answer', [WEATHER_ERROR, ]

        # 查询天气, 先查本地缓存
        _today = datetime.datetime.now().strftime('%Y-%m-%d')
        with redis.Redis(connection_pool=qa.redis_pool) as _redis:
            _json = _redis.get('api_tool_ask:weather:cache:%s:%s' % (_match_city_code, _today))
            if _json is None:
                # 要进行查询
                _api_back = NetTool.restful_api_call(
                    'http://t.weather.sojson.com/api/weather/city/%s' % _match_city_code,
                    back_type='text', logger=qa.logger
                )
                if _api_back['is_success']:
                    _json = _api_back['back_object']
                    _wdata = json.loads(_json)
                    if _wdata['status'] == 200:
                        # 存入缓存，一天到期
                        _redis.set(
                            'api_tool_ask:weather:cache:%s:%s' % (_match_city_code, _today),
                            _json, ex=86400
                        )
                    else:
                        return 'answer', [WEATHER_ERROR, ]
                else:
                    # 获取失败
                    return 'answer', [WEATHER_ERROR, ]
            else:
                _wdata = json.loads(_json)

        # 返回结果
        _end_str = ''  # 结束语
        if _match_day == 0:
            _end_str = '湿度%s, PM2.5: %s, 空气质量%s, %s, ' % (
                _wdata['data']['shidu'], _wdata['data']['pm25'], _wdata['data']['quality'],
                _wdata['data']['ganmao']
            )

        _answer = '亲, %s%s的天气%s, 吹%s%s, %s, %s, %s%s' % (
            _wdata['cityInfo']['city'], _wdata['data']['forecast'][_match_day]['ymd'],
            _wdata['data']['forecast'][_match_day]['type'],
            _wdata['data']['forecast'][_match_day]['fl'], _wdata['data']['forecast'][_match_day]['fx'],
            _wdata['data']['forecast'][_match_day]['high'], _wdata['data']['forecast'][_match_day]['low'],
            _end_str, _wdata['data']['forecast'][_match_day]['notice']
        )

        return 'answer', [_answer, ]

    #############################
    # 内部函数
    #############################
    @classmethod
    def _load_city_data(cls, loader, qa_manager: QAManager, qa: QA, **kwargs):
        """
        装载城市数据

        @param {QAServerLoader} loader - 服务装载器
        @param {QAManager} qa_manager - 数据管理
        @param {QA} qa - 问答服务
        """
        _logger = loader.logger
        if qa.use_redis:
            # 装载文件到内存
            _file = os.path.join(
                os.path.dirname(__file__), CITY_DATA_PATH, CITY_DATA_FILENAME
            )
            with open(_file, 'r', encoding='utf-8') as _fd:
                _city_data = json.load(_fd)

            # 数据排序
            _city_data.sort(key=lambda city: city['pid'])

            with redis.Redis(connection_pool=qa.redis_pool) as _redis:
                _last_import_time = _redis.hget('api_tool_ask:weather:city_data:0', 'ctime')
                if not CITY_DATA_FORCE_UPDATE and _last_import_time is not None and datetime.datetime.strptime(_last_import_time, '%Y-%m-%d %H:%M:%S') >= datetime.datetime.strptime(_city_data[0]['ctime'], '%Y-%m-%d %H:%M:%S'):
                    if _logger is not None:
                        _logger.info('City data not imported, redis data is new!')
                    return
                else:
                    if _last_import_time is not None:
                        # 清除原来的数据
                        _keys = _redis.keys('api_tool_ask:weather:city_data:*')
                        _redis.delete(*_keys)

                # 遍历执行导入操作
                _tree = dict()  # 用于找上级节点的清单的字典树, 注意前提是导入的json文件的顺序必须是父节点排在前面
                for _city in _city_data:
                    # 清理数据，None转为''
                    for _key in _city.keys():
                        if _city[_key] is None:
                            _city[_key] = ''

                    # 处理父节点清单, _tree上每个id都有自己的父节点清单
                    if _city['pid'] == 0:
                        # 没有父节点
                        _tree[_city['id']] = ''
                    else:
                        # 兼容数据中有些上级地区不存在
                        _pplist = _tree.get(_city['pid'], '')
                        _tree[_city['id']] = '"%d"%s%s' % (
                            _city['pid'], '' if _pplist == '' else ',', _pplist
                        )

                    # 添加信息
                    _redis.hset('api_tool_ask:weather:city_data:%d' % _city['id'], mapping=_city)

                    # 中文检索索引
                    _index_words = [_city['city_name']]
                    if _city['city_name'][-1:] in ['省', '市', '县', '区']:
                        # 去掉这些描述进行匹配
                        _index_words.append(_city['city_name'][0: -1])

                    # 添加索引信息
                    _index_value = str([
                        _city['city_code'],
                        eval('[%s]' % _tree[_city['id']])
                    ])
                    for _word in _index_words:
                        _redis.hset(
                            'api_tool_ask:weather:city_data:index:%s' % _word,
                            mapping={_city['id']: _index_value}
                        )

                    if _logger is not None:
                        _logger.debug(
                            'City data imported [%d][%s][%s]' % (
                                _city['id'], _city['city_code'], _city['city_name']
                            )
                        )

                # 全部导完后提示
                if _logger is not None:
                    _logger.info('City data import success!')
        else:
            if _logger is not None:
                _logger.info('City data not imported, Need redis support!')

    @classmethod
    def _search_city(cls, ns_words: list, redis_connection: redis.Redis) -> list:
        """
        根据地名列表匹配城市

        @param {list} ns_words - 地名列表
        @param {Redis} redis_connection - redis连接对象

        @returns {list} - 返回匹配到的地区列表
            [
                [id, [city_code, [parent_id_list]]],
            ]
        """
        _match_dict = dict()
        _ids = []
        for _word in ns_words:
            _match_index = redis_connection.hgetall(
                'api_tool_ask:weather:city_data:index:%s' % _word
            )
            if len(_match_index) == 0 and _word[-1:] in ['省', '市', '县', '区']:
                _match_index = redis_connection.hgetall(
                    'api_tool_ask:weather:city_data:index:%s' % _word[-1:]
                )
            # 遍历返回的结果放入字典，后续进行匹配删除
            for _id in _match_index.keys():
                _match_dict[_id] = [_id, eval(_match_index[_id])]
                _ids.append(_id)

        # 匹配删除不对的匹配项
        _deal_ids = copy.deepcopy(_ids)
        for _id in _ids:
            if _id not in _deal_ids:
                # 已被处理过
                continue

            _index = _match_dict[_id][1]
            if _index[0] == '':
                # 匹配到省份，删除不在这个省份所有数据
                for _sub_id in copy.deepcopy(_deal_ids):
                    if _sub_id != _id and _sub_id not in _match_dict[_sub_id][1][1]:
                        _deal_ids.remove(_sub_id)

                # 删除自身
                _deal_ids.remove(_id)
            else:
                # 有地区码，遍历剩余数据, 如果发现有包含自己的，删除自己
                for _sub_id in copy.deepcopy(_deal_ids):
                    if _sub_id != _id and _id in _match_dict[_sub_id][1][1]:
                        _deal_ids.remove(_id)
                        break

        # 返回匹配上的列表
        _match_list = []
        for _id in _deal_ids:
            _match_list.append(_match_dict[_id])

        return _match_list

    @classmethod
    def _get_city_full_name(cls, id: str, redis_connection: redis.Redis) -> str:
        """
        获取城市全名

        @param {str} id - 城市id
        @param {redis.Redis} redis_connection - redis连接

        @returns {str} - 返回的城市全名
        """
        _name = ''
        _id = id
        while True:
            _city = redis_connection.hgetall(
                'api_tool_ask:weather:city_data:%s' % _id
            )
            if len(_city) == 0:
                break

            _name = '%s%s' % (_city.get('city_name', ''), _name)

            if _city.get('pid', '0') == '0':
                break

            _id = _city['pid']

        return _name

    @classmethod
    def _add_weather_db_config(cls, loader):
        """
        添加天气问答数据库配置
        """
        _logger = loader.logger
        # 检查配置是否已经增加
        if (StdQuestion.select()
                .where(
                    (StdQuestion.milvus_id == -1) & (StdQuestion.q_type ==
                                                     'context') & (StdQuestion.question == '天气问答')
        ).count()) > 0:
            if _logger is not None:
                _logger.info('Weather config already exists!')
            return

        # 插入标准问题
        _std_q = StdQuestion.create(
            q_type='context', milvus_id=-1, collection=WEATHER_COLLECTION,
            partition=WEATHER_PARTITION,
            question='天气问答'
        )

        # 插入问题答案
        Answer.create(
            std_question_id=_std_q.id, a_type='ask',
            type_param="['ApiToolAsk', 'weather', '%s', '%s', {}, 'true']" % (
                WEATHER_COLLECTION, WEATHER_PARTITION
            ),
            replace_pre_def='N',
            answer=WEATHER_ERROR
        )

        # 插入NLP意图识别配置
        NlpPurposConfigDict.create(
            action='天气查询',
            match_collection='', match_partition='',
            collection=WEATHER_COLLECTION,
            partition=WEATHER_PARTITION,
            std_question_id=_std_q.id,
            order_num=0,
            exact_match_words='[]', exact_ignorecase='N',
            match_words="['天气', '今天天气']",
            ignorecase='N', word_scale=0.0,
            info="['InitInfo', 'get_wordclass_list', {'condition': [{'key': 'time', 'class': ['t']}, {'key': 'addr', 'class': ['ns']}]}]",
            check="['InitCheck', 'check_by_nest', {'next': {'天气': ['真好', '不错', '真差']}, }]"
        )

    @classmethod
    def _get_addr_by_ip(cls, ip: str, qa: QA) -> str:
        """
        尝试通过ip地址获取地址信息

        @param {str} ip - 要查询的ip地址

        @returns {str} - 匹配到的地址
        """
        _addr = ''
        _api_back = NetTool.restful_api_call(
            'https://restapi.amap.com/v3/ip?key=0113a13c88697dcea6a445584d535837',
            back_type='json', logger=qa.logger,
            json=None if ip == '127.0.0.1' else {'ip': ip}
        )
        if _api_back['is_success'] and _api_back['back_object']['status'] == "1":
            _addr = _api_back['back_object']['province'] + _api_back['back_object']['city']

        return _addr


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))
