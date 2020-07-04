#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
初始化QA问答服务
@module loader
@file loader.py
"""

import os
import sys
import inspect
import datetime
from flask_cors import CORS
from flask import Flask, request, send_file, jsonify
from flask_restful import reqparse
from werkzeug.routing import Rule, Map
from HiveNetLib.base_tools.file_tool import FileTool
from HiveNetLib.base_tools.import_tool import ImportTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.restful_api import FlaskTool, Qa, QaDataManager
from chat_robot.lib.data_manager import QAManager
from chat_robot.lib.qa import QA
from chat_robot.lib.nlp import NLP


__MOUDLE__ = 'loader'  # 模块名
__DESCRIPT__ = u'初始化QA问答服务'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.07.02'  # 发布日期


class QAServerLoader(object):
    """
    QA问答服务装载器
    """

    def __init__(self, server_config: dict, **kwargs):
        """
        初始化QA问答服务

        @param {dict} server_config - 服务配置字典
        """
        self.debug = server_config.get('debug', True)
        self.server_config = server_config
        self.app = Flask(__name__)
        CORS(self.app)
        self.app.debug = self.debug
        self.app.send_file_max_age_default = datetime.timedelta(seconds=1)  # 设置文件缓存1秒

        # 插件处理
        self.extend_plugin_path = self.server_config.get('extend_plugin_path', '')
        self.execute_path = self.server_config['execute_path']
        # plugins函数字典，格式为{'type':{'class_name': {'fun_name': fun, }, },}
        self.plugins = dict()
        self.load_plugins(os.path.join(self.execute_path, 'plugins'))
        if self.extend_plugin_path != '':
            if self.extend_plugin_path[0:1] == '.':
                # 相对路径
                self.extend_plugin_path = os.path.join(self.execute_path, self.extend_plugin_path)

            self.load_plugins(self.extend_plugin_path)

        # 装载数据管理模块
        self.qa_manager = QAManager(
            self.server_config['answerdb'], self.server_config['milvus'],
            self.server_config['bert_client'], debug=self.server_config['debug'],
            excel_batch_num=self.server_config['excel_batch_num'],
            excel_engine=self.server_config['excel_engine']
        )

        # 装载NLP
        _nlp_config = self.server_config['nlp_config']
        self.nlp = NLP(
            plugins=self.plugins, data_manager_para=self.qa_manager.DATA_MANAGER_PARA,
            set_dictionary=None if _nlp_config['set_dictionary'] == '' else _nlp_config['set_dictionary'],
            user_dict=None if _nlp_config['user_dict'] == '' else _nlp_config['user_dict'],
            enable_paddle=_nlp_config['enable_paddle'],
            parallel_num=_nlp_config.get('parallel_num', None)
        )

        # 初始化QA模块
        self.qa = QA(
            self.qa_manager, self.nlp, self.server_config['execute_path'], plugins=self.plugins,
            qa_config=self.server_config['qa_config'], debug=self.server_config['debug'],
        )

        # 动态加载路由
        self.api_class = [Qa, QaDataManager]
        if self.server_config['enable_client']:
            # 静态文件路径
            _client_path = self.server_config['client_path']
            if _client_path[0:1] == '.':
                # 相对路径
                _client_path = os.path.realpath(
                    os.path.join(self.execute_path, _client_path)
                )
            if self.debug:
                print('client path: %s' % _client_path)

            self.app.static_folder = os.path.join(_client_path, 'static')
            self.app.static_url_path = '/static/'

            # 加入客户端主页
            self.app.url_map.add(
                Rule('/', endpoint='client', methods=['GET'])
            )
            self.app.view_functions['client'] = self._client_view_function

        FlaskTool.add_route_by_class(self.app, self.api_class)
        if self.app.debug:
            print(self.app.url_map)

    #############################
    # 公共函数
    #############################

    def start_restful_server(self):
        """
        启动Restful Api服务
        """
        self.app.run(port=self.server_config['port'])

    #############################
    # 内部工具函数
    #############################

    def load_plugins(self, path: str):
        """
        装载job运行插件

        @param {str} path - 插件所在目录
        """
        _file_list = FileTool.get_filelist(path=path, regex_str=r'.*\.py$', is_fullname=False)
        for _file in _file_list:
            if _file == '__init__.py':
                continue

            # 执行加载
            _module = ImportTool.import_module(_file[0: -3], extend_path=path, is_force=True)
            _clsmembers = inspect.getmembers(_module, inspect.isclass)
            for (_class_name, _class) in _clsmembers:
                if _module.__name__ != _class.__module__:
                    # 不是当前模块定义的函数
                    continue

                # 判断类型
                _type_fun = getattr(_class, 'plugin_type', None)
                if _type_fun is None or not callable(_type_fun):
                    # 不是标准的插件类
                    continue

                _plugin_type = _type_fun()
                self.plugins.setdefault(_plugin_type, dict())
                self.plugins[_plugin_type][_class_name] = dict()
                if self.debug:
                    print('QAServerLoader.load_plugins add [%s] plugin file[%s] class[%s]:' % (
                        _plugin_type, _file, _class_name))

                for _name, _value in inspect.getmembers(_class):
                    if not _name.startswith('_') and callable(_value) and _name not in ['plugin_type']:
                        self.plugins[_plugin_type][_class_name][_name] = _value
                        if self.debug:
                            print('    add fun[%s]' % _name)

    #############################
    # 内部函数
    #############################

    def _client_view_function(self):
        return self.app.send_static_file('index.html')  # index.html在static文件夹下


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))
