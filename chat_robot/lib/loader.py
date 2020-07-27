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
import math
import redis
from flask_cors import CORS
from flask import Flask, request, send_file, jsonify
from flask_restful import reqparse
from werkzeug.routing import Rule, Map
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from HiveNetLib.simple_log import Logger
from HiveNetLib.base_tools.file_tool import FileTool
from HiveNetLib.base_tools.import_tool import ImportTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.restful_api import FlaskTool, Qa, QaDataManager, Client, TokenServer
from chat_robot.lib.answer_db import RestfulApiUser
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

    def __init__(self, server_config: dict, app: Flask = None, **kwargs):
        """
        初始化QA问答服务

        @param {dict} server_config - 服务配置字典
        @param {Flask} app=None - 服务
        """
        self.debug = server_config.get('debug', True)
        self.execute_path = server_config['execute_path']

        # 日志处理
        self.logger: Logger = None
        if 'logger' in server_config.keys():
            _logger_config = server_config['logger']
            if len(_logger_config['conf_file_name']) > 0 and _logger_config['conf_file_name'][0] == '.':
                # 相对路径
                _logger_config['conf_file_name'] = os.path.join(
                    self.execute_path, _logger_config['conf_file_name']
                )
            if len(_logger_config['logfile_path']) > 0 and _logger_config['logfile_path'][0] == '.':
                # 相对路径
                _logger_config['logfile_path'] = os.path.join(
                    self.execute_path, _logger_config['logfile_path']
                )
            self.logger = Logger.create_logger_by_dict(_logger_config)

        self.server_config = server_config
        self.app = app
        if self.app is None:
            self.app = Flask(__name__)
            CORS(self.app)

        self.app.debug = self.debug
        self.app.send_file_max_age_default = datetime.timedelta(seconds=1)  # 设置文件缓存1秒
        self.app.config['JSON_AS_ASCII'] = False  # 显示中文
        # 上传文件大小限制
        self.app.config['MAX_CONTENT_LENGTH'] = math.floor(
            self.server_config['max_upload_size'] * 1024 * 1024
        )

        # 插件字典，先定义清单，启动前完成加载
        self.extend_plugin_path = self.server_config.get('extend_plugin_path', '')
        self.plugins = dict()

        # 装载数据管理模块
        self.qa_manager = QAManager(
            self.server_config['answerdb'], self.server_config['milvus'],
            self.server_config['bert_client'], logger=self.logger,
            excel_batch_num=self.server_config['excel_batch_num'],
            excel_engine=self.server_config['excel_engine']
        )

        # 装载NLP
        _nlp_config = self.server_config['nlp_config']
        _user_dict = None
        if _nlp_config['user_dict'] != '':
            _user_dict = _nlp_config['user_dict']
            if _user_dict.startswith('.'):
                # 相对路径
                _user_dict = os.path.join(self.execute_path, _user_dict)
        _set_dictionary = None
        if _nlp_config['set_dictionary'] != '':
            _set_dictionary = _nlp_config['set_dictionary']
            if _set_dictionary.startswith('.'):
                # 相对路径
                _set_dictionary = os.path.join(self.execute_path, _set_dictionary)
        self.nlp = NLP(
            plugins=self.plugins, data_manager_para=self.qa_manager.DATA_MANAGER_PARA,
            set_dictionary=None if _nlp_config['set_dictionary'] == '' else _nlp_config['set_dictionary'],
            user_dict=_user_dict,
            enable_paddle=_nlp_config['enable_paddle'],
            parallel_num=_nlp_config.get('parallel_num', None),
            logger=self.logger
        )

        # 初始化QA模块
        self.qa = QA(
            self.qa_manager, self.nlp, self.server_config['execute_path'], plugins=self.plugins,
            qa_config=self.server_config['qa_config'], redis_config=self.server_config['redis'],
            logger=self.logger
        )

        # 动态加载路由
        self.api_class = [Qa, QaDataManager]

        # 完成插件的加载
        # plugins函数字典，格式为{'type':{'class_name': {'fun_name': fun, }, },}
        self.load_plugins(os.path.join(self.execute_path, 'plugins'))
        if self.extend_plugin_path != '':
            if self.extend_plugin_path[0:1] == '.':
                # 相对路径
                self.extend_plugin_path = os.path.join(self.execute_path, self.extend_plugin_path)

            self.load_plugins(self.extend_plugin_path)

        # 安全关联
        _security = self.server_config['security']
        self.token_serializer = Serializer(
            _security['secret_key'], _security['token_expire'],
            salt=bytes(_security['salt'], encoding='utf-8'),
            algorithm_name=_security['algorithm_name']
        )
        # 验证ip白名单处理
        _security['token_server_auth_ip_list'] = _security['token_server_auth_ip_list'].split(',')

        # 增加令牌服务的路由
        if _security['enable_token_server']:
            self.api_class.append(TokenServer)

        # 增加静态路径
        _static_path = self.server_config['static_path']
        if _static_path[0:1] == '.':
            # 相对路径
            _static_path = os.path.realpath(
                os.path.join(self.execute_path, _static_path)
            )

        self.app.static_folder = os.path.join(_static_path, 'static')
        self.app.static_url_path = '/static/'

        # 增加客户端路由
        if self.server_config['enable_client']:
            # 客户端路由api服务
            self.api_class.append(Client)

            # 创建测试用户
            if self.server_config['add_test_login_user']:
                _user = RestfulApiUser.get_or_none(RestfulApiUser.user_name == 'test')
                if _user is None:
                    self.register_user('test', '123456')

            # 加入客户端主页
            self.app.url_map.add(
                Rule('/', endpoint='client', methods=['GET'])
            )
            self.app.view_functions['client'] = self._client_view_function

        FlaskTool.add_route_by_class(self.app, self.api_class)
        self._log_debug(str(self.app.url_map))

    #############################
    # 公共函数
    #############################

    def start_restful_server(self):
        """
        启动Restful Api服务
        """
        self.app.run(**self.server_config['flask'])

    #############################
    # 安全认证相关处理
    #############################
    def register_user(self, user_name: str, password: str) -> int:
        """
        注册登陆用户

        @param {str} user_name - 登陆用户名
        @param {str} password - 登陆密码

        @returns {int} - 用户id
        """
        _user = RestfulApiUser.create(
            user_name=user_name, password_hash=generate_password_hash(password)
        )
        return _user.id

    def login(self, user_name: str, password: str, is_generate_token: bool = True) -> dict:
        """
        用户登陆

        @param {str} user_name - 登陆用户名
        @param {str} password - 登陆密码
        @param {bool} is_generate_token=True - 是否产生令牌

        @returns {dict} - 返回用户信息
            status - 状态， 00000-成功， 10001-用户名不存在，10002-用户名密码错误
            user_id - 用户id
            token - 可用的token
        """
        _back = {
            'status': '00000',
            'user_id': 0,
            'token': ''
        }
        _user = RestfulApiUser.get_or_none(RestfulApiUser.user_name == user_name)
        if _user is None:
            _back['status'] = '10001'
        else:
            if check_password_hash(_user.password_hash, password):
                _back['user_id'] = _user.id
                if is_generate_token:
                    _back['token'] = self.generate_token(_user.id)
            else:
                _back['status'] = '10002'

        return _back

    def generate_token(self, user_id: int, last_token: str = None) -> str:
        """
        创建一个新的token

        @param {int} user_id - 用户id
        @param {str} last_token=None - 上一个有效token，用于消除token, 只有redis模式才支持

        @returns {str} - 返回新的token
        """
        # 先创建新的token
        _token = self.token_serializer.dumps({'user_id': user_id}).decode('ascii')

        if self.qa.use_redis:
            # 存入到redis缓存
            with redis.Redis(connection_pool=self.qa.redis_pool) as _redis:
                _redis.set(
                    'chat_robot:security:token:%d:%s' % (user_id, _token), 'true',
                    ex=self.server_config['security']['token_expire']
                )

                # 清除原来的token
                if last_token is not None:
                    _redis.delete('chat_robot:security:token:%d:%s' % (user_id, last_token))

        return _token

    def verify_token(self, user_id: int, token: str) -> bool:
        """
        验证连接的token是否正常

        @param {int} user_id - 用户id
        @param {str} token - 客户端传入的token

        @returns {bool} - 返回验证结果
        """
        if not self.server_config['security']['enable_token']:
            return True

        if self.qa.use_redis:
            # 使用redis方式验证
            with redis.Redis(connection_pool=self.qa.redis_pool) as _redis:
                _is_exists = _redis.get('chat_robot:security:token:%d:%s' % (user_id, token))
                if _is_exists is None:
                    return False
                else:
                    return True
        else:
            try:
                self.token_serializer.loads(token)
            except:
                return False

        return True

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
                self._log_debug(
                    'add [%s] plugin file[%s] class[%s]:' % (_plugin_type, _file, _class_name),
                )

                for _name, _value in inspect.getmembers(_class):
                    if not _name.startswith('_') and callable(_value) and _name not in ['plugin_type']:
                        if _name == 'initialize':
                            # 装载时执行一次初始化
                            _value(self, self.qa_manager, self.qa)
                        else:
                            self.plugins[_plugin_type][_class_name][_name] = _value
                            self._log_debug('    add fun[%s]' % _name)

    #############################
    # 内部函数
    #############################

    def _client_view_function(self):
        return self.app.send_static_file('index.html')  # index.html在static文件夹下

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
