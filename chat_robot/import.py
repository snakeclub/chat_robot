#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
数据导入模块
@module import
@file import.py
"""

import os
import sys
import getopt
from HiveNetLib.simple_xml import SimpleXml
from HiveNetLib.base_tools.file_tool import FileTool
from HiveNetLib.base_tools.run_tool import RunTool
from HiveNetLib.simple_log import Logger
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from chat_robot.lib.data_manager import QAManager


__MOUDLE__ = 'import'  # 模块名
__DESCRIPT__ = u'数据导入模块'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.07.04'  # 发布日期


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    _opts = RunTool.get_kv_opts()

    # 获取配置信息值
    _import = _opts.get('import', None)  # 要导入的excel文件
    _config = _opts.get('config', None)  # 指定配置文件
    _encoding = _opts.get('encoding', 'utf-8')  # 配置文件编码
    _truncate = (_opts.get('truncate', 'false') == 'true')  # 是否清空标志，与操作搭配使用
    _milvus = _opts.get('del_milvus', None)  # 要删除的问题分类清单，用,分隔
    _db = (_opts.get('del_db', 'false') == 'true')  # 要重置数据库

    # 获取配置文件信息
    _execute_path = os.path.realpath(FileTool.get_file_path(__file__))
    if _config is None:
        _config = os.path.join(_execute_path, 'conf/server.xml')

    _config_xml = SimpleXml(_config, encoding=_encoding)
    _server_config = _config_xml.to_dict()['server']

    # 日志对象
    _logger: Logger = None
    if 'logger' in _server_config.keys():
        _logger = Logger.create_logger_by_dict(_server_config['logger'])

    # 连接数据库操作对象
    _qa_manager = QAManager(
        _server_config['answerdb'], _server_config['milvus'], _server_config['bert_client'],
        logger=_logger, excel_batch_num=_server_config['excel_batch_num'],
        excel_engine=_server_config['excel_engine']
    )

    # 执行操作
    if _import is not None:
        # 导入excel文件
        _qa_manager.import_questions_by_xls(
            _import, reset_questions=_truncate
        )
    elif _milvus is not None:
        # 删除milvus分类
        _list = _milvus.split(',')
        _qa_manager.delete_milvus_collection(_list, truncate=_truncate)
    elif _db:
        # 重置数据库
        _qa_manager.reset_db()
    else:
        print('参数错误！')
