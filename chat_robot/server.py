#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
聊天机器人服务端
@module server
@file server.py
"""

import os
import sys
import copy
import getopt
from HiveNetLib.simple_xml import SimpleXml
from HiveNetLib.base_tools.file_tool import FileTool
from HiveNetLib.base_tools.run_tool import RunTool

# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
from chat_robot.lib.loader import QAServerLoader


__MOUDLE__ = 'server'  # 模块名
__DESCRIPT__ = u'聊天机器人服务端'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.06.17'  # 发布日期


def start_server(**kwargs):
    """
    启动聊天服务端应用
    """
    SERVER_CONFIG = RunTool.get_global_var('SERVER_CONFIG')
    _loader = QAServerLoader(SERVER_CONFIG)
    RunTool.set_global_var('QA_LOADER', _loader)

    # 启动服务
    _loader.start_restful_server()


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            "p:conf:e:d",
            ["port=", "config=", 'encoding=', 'debug'],
        )
    except:
        print("Usage: server.py -p <port> -c")
        sys.exit(2)

    # 获取配置信息值
    _port = None  # 指定服务端口
    _client = True  # 是否启动客户端(测试应用)
    _config = None  # 指定配置文件
    _encoding = 'utf-8'  # 配置文件编码
    _debug = True  # 是否debug模式
    for opt_name, opt_value in opts:
        if opt_name in ("-p", "--port"):
            _port = int(opt_value)
        elif opt_name in ("-conf", "--config"):
            _config = opt_value
        elif opt_name in ("-e", "--encoding"):
            _config = opt_value
        elif opt_name in ("-d", "--debug"):
            _debug = True

    # 获取配置文件信息
    _execute_path = os.path.realpath(FileTool.get_file_path(__file__))
    if _config is None:
        _config = os.path.join(_execute_path, 'conf/server.xml')

    _config_xml = SimpleXml(_config, encoding=_encoding)
    SERVER_CONFIG = _config_xml.to_dict()['server']
    if _port is not None:
        SERVER_CONFIG['port'] = _port
    SERVER_CONFIG['debug'] = _debug
    SERVER_CONFIG['config'] = _config
    SERVER_CONFIG['encoding'] = _encoding
    SERVER_CONFIG['execute_path'] = _execute_path

    # 将服务配置放入全局变量
    RunTool.set_global_var('SERVER_CONFIG', SERVER_CONFIG)

    # 启动服务
    start_server()
