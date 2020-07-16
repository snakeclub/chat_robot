#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
对外提供的restful api服务
@module restful_api
@file restful_api.py
"""

import os
import sys
import re
import random
import inspect
import traceback
import uuid
import datetime
from functools import wraps
from flask import Flask, request, jsonify
from flask_httpauth import HTTPTokenAuth
from werkzeug.routing import Rule
from HiveNetLib.base_tools.run_tool import RunTool
from HiveNetLib.base_tools.file_tool import FileTool
from HiveNetLib.base_tools.string_tool import StringTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
# from chat_robot.lib.loader import QAServerLoader
from chat_robot.lib.answer_db import UploadFileConfig


__MOUDLE__ = 'restful_api'  # 模块名
__DESCRIPT__ = u'对外提供的restful api服务'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.06.17'  # 发布日期


auth = RunTool.get_global_var('HTTP_TOKEN_AUTH')
if auth is None:
    auth = HTTPTokenAuth(scheme='JWT')
    RunTool.set_global_var('HTTP_TOKEN_AUTH', auth)


class FlaskTool(object):
    """
    Flash工具类，提供路由，内容解析等通用处理功能
    """
    @classmethod
    def add_route_by_class(cls, app: Flask, class_objs: list):
        """
        通过类对象动态增加路由

        @param {Flask} app - 要增加服务的Flask应用
        @param {list} class_objs - Api类对象清单
        """
        for _class in class_objs:
            _class_name = _class.__name__
            # 遍历所有函数
            for _name, _value in inspect.getmembers(_class):
                if not _name.startswith('_') and callable(_value):
                    _endpoint = '%s.%s' % (_class_name, _name)
                    _route = '/api{$ver$}/%s/%s' % (_class_name, _name)
                    _methods = None
                    _ver = ''
                    _para_list = RunTool.get_function_parameter_defines(_value)
                    for _para in _para_list:
                        if _para['name'] == 'methods':
                            # 指定了处理方法
                            _methods = _para['default']
                        elif _para['name'] == 'ver':
                            # 有指定ver的入参，在路由api后面进行变更
                            _ver = '/<ver>'
                        else:
                            _type = ''
                            if _para['annotation'] == int:
                                _type = 'int:'
                            elif _para['annotation'] == float:
                                _type = 'float:'

                            _route = '%s/<%s%s>' % (_route, _type, _para['name'])

                    # 创建路由
                    app.url_map.add(
                        Rule(_route.replace('{$ver$}', _ver), endpoint=_endpoint, methods=_methods)
                    )
                    if _ver != '':
                        # 也支持不传入版本的情况
                        app.url_map.add(
                            Rule(_route.replace('{$ver$}', ''),
                                 endpoint=_endpoint, methods=_methods)
                        )

                    app.view_functions[_endpoint] = _value

    @classmethod
    def db_connect(cls, func):
        """
        处理数据库连接打开和关闭的修饰符
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            _qa_loader = RunTool.get_global_var('QA_LOADER')
            _database = _qa_loader.qa_manager.database
            # 需要显式打开和关闭数据库连接，避免连接池连接数超最大数
            _database.connect()
            try:
                _ret = func(*args, **kwargs)
            finally:
                if not _database.is_closed():
                    _database.close()

            return _ret
        return wrapper

    @classmethod
    def log(cls, func):
        """
        登记日志的修饰符
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            _fun_name = func.__name__
            _start_time = datetime.datetime.now()
            _qa_loader = RunTool.get_global_var('QA_LOADER')
            _IP = request.remote_addr
            _trace_id = str(uuid.uuid1())
            _enconding = 'utf-8' if request.charset == '' else request.charset
            _log_str = '[API-FUN:%s][IP:%s][INF-RECV][TRACE-API:%s]%s %s\n%s%s' % (
                _fun_name, _IP, _trace_id, request.method, request.path,
                str(request.headers),
                str(request.data, encoding=_enconding) if request.mimetype.startswith('text/') or request.mimetype in [
                    'application/json', 'application/xml'] else ''
            )
            if _qa_loader.logger:
                _qa_loader.logger.debug(_log_str, extra={'callFunLevel': 1})

            # 执行函数
            _ret = func(*args, **kwargs)

            _enconding = 'utf-8' if _ret.charset == '' else _ret.charset
            _log_str = '[API-FUN:%s][IP:%s][INF-RET][TRACE-API:%s][USE:%s]%s%s' % (
                _fun_name, _IP, _trace_id, str(
                    (datetime.datetime.now() - _start_time).total_seconds()),
                str(_ret.headers),
                str(_ret.data, encoding=_enconding) if _ret.mimetype.startswith('text/') or _ret.mimetype in [
                    'application/json', 'application/xml'] else ''
            )
            if _qa_loader.logger:
                _qa_loader.logger.debug(_log_str, extra={'callFunLevel': 1})
            return _ret
        return wrapper

    @classmethod
    def get_token_auth(cls) -> HTTPTokenAuth:
        """
        获取HTTPTokenAuth对象

        @returns {HTTPTokenAuth} - 返回唯一的HTTPTokenAuth对象
        """
        _auth = RunTool.get_global_var('HTTP_TOKEN_AUTH')
        if _auth is None:
            _auth = HTTPTokenAuth(scheme='JWT')
            RunTool.set_global_var('HTTP_TOKEN_AUTH', _auth)

        return _auth


@auth.verify_token
def verify_token(token: str):
    """
    进行token的验证，如果需要实现自定义的验证方式，请重载该方法

    @param {str} token - 要验证的token

    @returns {bool} - 验证结果
    """
    _loader = RunTool.get_global_var('QA_LOADER')
    if _loader is None:
        return False

    return _loader.verify_token(int(request.headers.get('UserID', 0)), token)


#############################
# Restful Api 的实现类，只要定义了，通过FlaskTool加入到路由就可以完成接口的发布
# 规则如下：
#        1、每个非'_'开头的静态函数为一个对外API服务；
#        2、可以通过函数最后的methods参数指定api的动作，例如指定GET、POST等，例如['GET']、['GET', 'POST']
#        3、可以通过函数最后的ver参数指定api支持版本号，注意需要设置当调用不传入版本号时的默认值
#        4、函数的入参定义会反映到路由中（methods/ver参数除外）
#    例如：
#        Test(a:str, b:int, methods=['GET'], ver='0.5')会自动配置路由为：
#            Rule('/api/<ver>/ClassName/Test/<a>/<int:b>', endpoint='ClassName.Test', methods=['GET'])
#            Rule('/api/ClassName/Test/<a>/<int:b>', endpoint='ClassName.Test', methods=['GET'])
#        Test(a:str, b:int, methods=['GET'])会自动配置路由为：
#            Rule('/api/ClassName/Test/<a>/<int:b>', endpoint='ClassName.Test', methods=['GET'])
#    函数内部可以使用以下方法获取传入参数：
#        1、通过request.args['key']，获取'?key=value&key1=value1'这类的传参
#        2、通过request.json['key']，获取在body传入的json结构对应的key的值，例如
#            request.json['id']可以获取body中的“{"id": 1234, "info": "测试\\n一下"}” 的id的值
#            注意：报文头的Content-Type必须为application/json
#        3、通过request.files['file']，获取上传的文件
#    函数可以通过jsonify将python对象转换为json字符串返回到请求端
#############################


class Client(object):
    """
    客户端产生并获取token的后门，正常情况token应该在客户登陆后产生并反馈给客户端
    """
    @classmethod
    @FlaskTool.log
    @FlaskTool.db_connect
    def login(cls, methods=['POST']):
        """
        执行用户登陆
        传入信息为json字典，例如:
            {
                'interface_seq_id': '(可选)客户端序号，客户端可传入该值来支持异步调用'
                'username': 'test',
                'password': '123456'
            }

        @return {str} - 返回回答的json字符串
            interface_seq_id : 回传客户端的接口请求id
            status : 处理状态
                00000 - 登陆成功
                10001 - 用户名密码验证失败
                2XXXX - 处理失败
            msg : 处理状态对应的描述
            user_id : int, 用户id
            token : 返回可用的token
        """
        _qa_loader = RunTool.get_global_var('QA_LOADER')
        _interface_seq_id = ''
        if request.json is not None:
            _interface_seq_id = request.json.get('interface_seq_id', '')
        try:
            _ret_json = {
                'interface_seq_id': _interface_seq_id,
                'status': '00000',
                'msg': 'success'
            }

            _back = _qa_loader.login(
                request.json['username'],
                request.json['password']
            )

            _ret_json['status'] = _back['status']
            if _back['status'] == '00000':
                _ret_json['user_id'] = _back['user_id']
                _ret_json['token'] = _back['token']
            elif _back['status'] == '10000':
                _ret_json['msg'] = 'username not exists!'
            else:
                _ret_json['msg'] = 'username or password error!'
        except:
            if _qa_loader.logger:
                _qa_loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json = {
                'interface_seq_id': _interface_seq_id,
                'status': '20001',
                'msg': '生成session id出现异常'
            }

        # 返回结果
        return jsonify(_ret_json)


class TokenServer(object):
    """
    令牌服务器（支持其他系统后台产生有效令牌）
    """
    @classmethod
    @FlaskTool.log
    @FlaskTool.db_connect
    def GenerateUserToken(cls, methods=['POST']):
        """
        生成客户端使用的令牌
        传入信息为json字典，例如:
            {
                'interface_seq_id': '(可选)客户端序号，客户端可传入该值来支持异步调用'
                'username': 'API用户的登陆用户名（非客户用户）, 如果验证方式是密码形式提供',
                'password': 'API用户的登陆密码（非客户用户）, 如果验证方式是密码形式提供',
                'user_id': '必须，要生成的令牌的用户id'
                'last_token': 如果需要失效原token，送入
            }

        @return {str} - 返回回答的json字符串
            interface_seq_id : 回传客户端的接口请求id
            status : 处理状态
                00000 - 登陆成功
                10001 - 用户名密码验证失败
                10002 - 访问IP验证失败
                2XXXX - 处理失败
            msg : 处理状态对应的描述
            user_id : int, 令牌对应的客户用户id
            token : 返回可用的token
        """
        _qa_loader = RunTool.get_global_var('QA_LOADER')
        _interface_seq_id = ''
        if request.json is not None:
            _interface_seq_id = request.json.get('interface_seq_id', '')
        try:
            _ret_json = {
                'interface_seq_id': _interface_seq_id,
                'status': '00000',
                'msg': 'success',
                'user_id': request.json['user_id']
            }

            # 进行权限验证
            _security = _qa_loader.server_config['security']
            if _security['token_server_auth_type'] == 'ip':
                # ip验证模式
                if request.remote_addr not in _security['token_server_auth_ip_list']:
                    _ret_json['status'] = '10002'
                    _ret_json['msg'] = '访问IP验证失败'
            else:
                # 用户名密码验证
                _back = _qa_loader.login(
                    request.json['username'],
                    request.json['password'],
                    is_generate_token=False
                )

                _ret_json['status'] = _back['status']
                if _back['status'] != '00000':
                    if _back['status'] == '10001':
                        _ret_json['msg'] = 'username not exists!'
                    else:
                        _ret_json['msg'] = 'username or password error!'

            # 处理令牌生成
            if _back['status'] == '00000':
                _last_token = request.json.get('last_token', '')
                _ret_json['token'] = _qa_loader.generate_token(
                    request.json['user_id'],
                    last_token=_last_token if _last_token != '' else None
                )
        except:
            if _qa_loader.logger:
                _qa_loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json = {
                'interface_seq_id': _interface_seq_id,
                'status': '20001',
                'msg': '生成token出现异常'
            }

        # 返回结果
        return jsonify(_ret_json)


class Qa(object):
    """
    Qa问答服务
    """
    @classmethod
    @FlaskTool.log
    @FlaskTool.db_connect
    @auth.login_required
    def GenerateToken(cls, methods=['GET']):
        """
        生成新的token (/api/Qa/GenerateToken)
        如果是异步调用，可传入json字典，例如:
        {
            'interface_seq_id': '(可选)客户端序号，客户端可传入该值来支持异步调用'
        }

        @return {str} - 返回回答的json字符串
            interface_seq_id : 回传客户端的接口请求id
            status : 处理状态
                00000 - 成功
                2XXXX - 处理失败
            msg : 处理状态对应的描述
            token : 返回新生成的token
        """
        _qa_loader = RunTool.get_global_var('QA_LOADER')
        _interface_seq_id = ''
        if request.json is not None:
            _interface_seq_id = request.json.get('interface_seq_id', '')
        try:

            _ret_json = {
                'interface_seq_id': _interface_seq_id,
                'status': '00000',
                'msg': 'success',
            }

            _token = _qa_loader.generate_token(
                int(request.headers['UserId']),
                last_token=(request.headers['Authorization'][4:])
            )
            _ret_json['token'] = _token
        except:
            if _qa_loader.logger:
                _qa_loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json = {
                'interface_seq_id': _interface_seq_id,
                'status': '20001',
                'msg': '生成session id出现异常'
            }

        # 返回结果
        return jsonify(_ret_json)

    @classmethod
    @FlaskTool.log
    @FlaskTool.db_connect
    @auth.login_required
    def GetSessionId(cls, methods=['POST']):
        """
        获取用户Session并上传用户信息 (/api/Qa/GetSessionId)
        传入信息为json字典，例如:
            {
                'interface_seq_id': '(可选)客户端序号，客户端可传入该值来支持异步调用'
                'user_id': 1,
                'user_name': 'xxx'
            }

        @return {str} - 返回回答的json字符串
            interface_seq_id : 回传客户端的接口请求id
            status : 处理状态
                00000 - 成功
                2XXXX - 处理失败
            msg : 处理状态对应的描述
            session_id : 返回的session id
        """
        # 创建session并存入信息
        _qa_loader = RunTool.get_global_var('QA_LOADER')
        _interface_seq_id = ''
        if request.json is not None:
            _interface_seq_id = request.json.get('interface_seq_id', '')
        try:
            # 尝试加入IP地址
            if 'ip' not in request.json.keys():
                request.json['ip'] = request.remote_addr

            _session_id = _qa_loader.qa.generate_session(request.json)
            _ret_json = {
                'interface_seq_id': _interface_seq_id,
                'status': '00000',
                'msg': 'success',
                'session_id': _session_id
            }
        except:
            if _qa_loader.logger:
                _qa_loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json = {
                'interface_seq_id': _interface_seq_id,
                'status': '20001',
                'msg': '生成session id出现异常'
            }

        # 返回结果
        return jsonify(_ret_json)

    @classmethod
    @FlaskTool.log
    @FlaskTool.db_connect
    @auth.login_required
    def SearchAnswer(cls, methods=['POST']):
        """
        获取问题答案 (/api/Qa/SearchAnswer)
        传入信息为json字典，定义如下:
            {
                'interface_seq_id': '(可选)客户端序号，客户端可传入该值来支持异步调用'
                'session_id': GetSessionId获取的session id,
                'question': 客户的输入,
                'collection': 指定的问题分类，可不传
            }

        @return {str} - 返回回答的json字符串
            interface_seq_id : 回传客户端的接口请求id
            status : 处理状态
                00000 - 成功, 返回一条回答
                00001 - 成功, 返回上下文选择清单
                10001 - session id为必填
                10002 - session id不存在或已失效
                2XXXX - 处理失败
            msg : 处理状态对应的描述
            answer_type: 'text'或'json'，指示返回的答案是文本数组，还是一个json对象
            answers : 匹配答案
        """
        _qa_loader = RunTool.get_global_var('QA_LOADER')
        _interface_seq_id = ''
        if request.json is not None:
            _interface_seq_id = request.json.get('interface_seq_id', '')
        try:
            _ret_json = {
                'interface_seq_id': _interface_seq_id,
                'status': '00001',
                'msg': 'success',
            }
            _session_id = request.json.get('session_id', None)
            if _session_id is None:
                _ret_json['status'] = '10001'
                _ret_json['msg'] = 'session id is null'
                return jsonify(_ret_json)

            _question = request.json['question']
            _collection = request.json.get('collection', None)
            if _collection == '':
                _collection = None

            # 需要显式打开和关闭数据库连接，避免连接池连接数超最大数
            _answers = _qa_loader.qa.quession_search(_question, _session_id, _collection)

            # 处理返回类型
            if len(_answers) > 0 and type(_answers[0]) == dict:
                _ret_json['answer_type'] = 'json'
                _ret_json['answers'] = _answers[0]
            else:
                _ret_json['answer_type'] = 'text'
                _ret_json['answers'] = _answers
                if len(_answers) > 1:
                    _ret_json['status'] = '00001'
        except FileNotFoundError:
            if _qa_loader.logger:
                _qa_loader.logger.debug(
                    'Session not found: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json = {
                'interface_seq_id': _interface_seq_id,
                'status': '10002',
                'msg': 'session id 不存在'
            }
        except:
            if _qa_loader.logger:
                _qa_loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json = {
                'status': '20001',
                'msg': '获取答案出现异常'
            }

        return jsonify(_ret_json)

    @classmethod
    @FlaskTool.log
    @FlaskTool.db_connect
    @auth.login_required
    def UploadFile(cls, upload_type: str, note: str, interface_seq_id: str, methods=['POST']):
        """
        上传文件(单文件上传)  (/api/Qa/UploadFiles/<upload_type>/<note>/<interface_seq_id>)

        @param {str} upload_type - 文件类型，必须在UploadFileConfig表中有配置
        @param {str} note - 文件注解
        @param {str} interface_seq_id - 客户端序号，客户端可传入该值来支持异步调用

        @return {str} - 返回回答的json字符串
            status : 处理状态
                00000 - 成功, 返回一条回答
                10001 - 没有指定上传文件
                2XXXX - 处理失败
            msg : 处理状态对应的描述
            answer_type: 'text'或'json'，指示返回的答案是文本数组，还是一个json对象
            answers : 回答内容
            url : 文件上传后的url，含文件名和url路径
        """
        _ret_json = {
            'interface_seq_id': interface_seq_id,
            'status': '00000',
            'msg': 'success',
            'answer_type': 'text',
            'answers': [],
            'url': ''
        }
        _qa_loader = RunTool.get_global_var('QA_LOADER')
        try:
            if 'file' not in request.files or request.files['file'].filename == '':
                _ret_json['status'] = '10001'
                _ret_json['msg'] = 'No file upload!'
                return jsonify(_ret_json)

            # 获取上传类型配置
            _upload_config = UploadFileConfig.get_or_none(
                UploadFileConfig.upload_type == upload_type
            )
            if _upload_config is None:
                _ret_json['status'] = '10002'
                _ret_json['msg'] = 'upload type not exists!'
                return jsonify(_ret_json)

            # 检查文件大小
            if _upload_config.size > 0:
                if request.content_length > _upload_config.size * 1024 * 1024:
                    _ret_json['status'] = '10003'
                    _ret_json['msg'] = 'upload file size to large!'
                    return jsonify(_ret_json)

            # 检查文件类型是否支持
            _file = request.files['file']
            _old_filename = _file.filename
            _file_ext = FileTool.get_file_ext(_old_filename)
            _allow_ext = eval(_upload_config.exts.upper())
            if len(_allow_ext) > 0 and _file_ext.upper() not in _allow_ext:
                _ret_json['status'] = '10004'
                _ret_json['msg'] = 'Type [%s] not allow upload [.%s] file!' % (
                    upload_type, _file_ext
                )
                return jsonify(_ret_json)

            # 处理新的文件名
            def _replace_var_fun(m):
                _match_str = m.group(0)
                _value = None
                if _match_str.startswith('{$datetime='):
                    # 按格式化字符替换当前的时间
                    _key = _match_str[11:-2]
                    _value = datetime.datetime.now().strftime(_key)
                elif _match_str.startswith('{$uuid='):
                    # 指定uuid字符类型
                    _key = _match_str[7:-2]
                    str(uuid.uuid1())
                    _value = eval('str(uuid.uuid%s())' % _key)
                elif _match_str.startswith('{$random'):
                    # 产生指定两个整数之间的随机数，总位数与最大的数一致，左补零
                    _key = _match_str[8:-2]
                    _args = eval('(%s)' % _key)
                    _value = StringTool.fill_fix_string(
                        str(random.randint(*_args)), len(_args[1]), '0')
                elif _match_str.startswith('{$file_ext='):
                    # 原文件扩展名
                    _value = _file_ext
                elif _match_str.startswith('{$file_name='):
                    # 原文件指定位置的字符
                    _key = _match_str[12:-2]
                    _args = eval('(%s)' % _key)
                    if len(_args) > 1:
                        _value = _old_filename[_args[0]: _args[1]]
                    else:
                        _value = _old_filename[_args[0]:]

                if _value is not None:
                    return str(_value)
                else:
                    return _match_str

            if _upload_config.rename == '':
                _new_filename = _old_filename
            else:
                _new_filename = re.sub(
                    r'\{\$.+?\$\}', _replace_var_fun, _upload_config.rename, re.M
                )

            # 处理保存文件路径和url路径
            if _upload_config.url != '':
                _ret_json['url'] = '%s/%s' % (_upload_config.url, _new_filename)

            _save_path = os.path.realpath(os.path.join(
                _qa_loader.execute_path,
                _upload_config.save_path, _new_filename
            ))

            # 保存文件
            _file.save(_save_path)

            # 上传后处理
            _after = eval(_upload_config.after)
            if len(_after) > 0:
                _after_fun = _qa_loader.plugins['upload_after'][_after[0]][_after[1]]
                _status, _msg, _answers = _after_fun(
                    upload_type, note, _new_filename, _save_path, _ret_json['url'],
                    **_after[2]
                )
                _ret_json['status'] = _status
                _ret_json['msg'] = _msg
                if len(_answers) > 0 and type(_answers[0]) == dict:
                    _ret_json['answer_type'] = 'json'
                    _ret_json['answers'] = _answers[0]
                else:
                    _ret_json['answers'] = _answers
                if _ret_json['status'] != '00000':
                    # 后处理失败，删除文件
                    FileTool.remove_file(_save_path)
                    if _qa_loader.logger:
                        _qa_loader.logger.debug(
                            'remove upload file [dest:%s][source:%s] when after deal error[%s]: %s' % (
                                _new_filename, _old_filename, _status, _msg
                            )
                        )
        except:
            if _qa_loader.logger:
                _qa_loader.logger.error(
                    'Exception: %s' % traceback.format_exc(),
                    extra={'callFunLevel': 1}
                )
            _ret_json = {
                'interface_seq_id': interface_seq_id,
                'status': '20001',
                'msg': '上传文件异常'
            }

        return jsonify(_ret_json)


class QaDataManager(object):
    """
    QA问题答案管理对外提供的restful api服务类
    """
    #############################
    #
    #############################
    @classmethod
    @FlaskTool.log
    def Test(cls, a: str, b: int, ver: str = '1.5', methods=['GET']):
        """
        测试类
        """
        print(a, ': ', b)
        # 传参数
        if not request.args:
            print('not args')
        else:
            print(request.args)
            print(request.args['key2'])

        print(request.json['info'])

        _return = {
            'a': a,
            'b': b,
            'ver': ver,
            'id': request.json['id'],
            'info': request.json['info'],
        }

        return jsonify(_return)


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))
