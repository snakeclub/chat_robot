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
import inspect
import traceback
import uuid
import datetime
from functools import wraps
from flask import Flask, request, jsonify
from werkzeug.routing import Rule
from HiveNetLib.base_tools.run_tool import RunTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.qa import QA


__MOUDLE__ = 'restful_api'  # 模块名
__DESCRIPT__ = u'对外提供的restful api服务'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.06.17'  # 发布日期


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
    def log(cls, func):
        """
        登记日志的修饰符
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            _fun_name = func.__name__
            _start_time = datetime.datetime.now()
            _qa: QA = RunTool.get_global_var('QA_LOADER').qa
            _IP = request.remote_addr
            _trace_id = str(uuid.uuid1())
            _log_str = '[API-FUN:%s][IP:%s][INF-RECV][TRACE-API:%s]%s %s\n%s%s' % (
                _fun_name, _IP, _trace_id, request.method, request.path,
                str(request.headers), str(request.data, encoding='utf-8')
            )
            if _qa.logger:
                _qa.logger.debug(_log_str, extra={'callFunLevel': 1})

            # 执行函数
            _ret = func(*args, **kwargs)

            _log_str = '[API-FUN:%s][IP:%s][INF-RET][TRACE-API:%s][USE:%s]%s%s' % (
                _fun_name, _IP, _trace_id, str(
                    (datetime.datetime.now() - _start_time).total_seconds()),
                str(_ret.headers), str(_ret.data, encoding='utf-8')
            )
            if _qa.logger:
                _qa.logger.debug(_log_str, extra={'callFunLevel': 1})
            return _ret
        return wrapper


class Qa(object):
    """
    Qa问答服务
    """
    @classmethod
    @FlaskTool.log
    def GetSessionId(cls, methods=['POST']):
        """
        获取用户Session并上传用户信息
        传入信息为json字典，例如:
            {
                'user_id': 1,
                'user_name': 'xxx'
            }

        @return {str} - 返回回答的json字符串
            status : 处理状态
                00000 - 成功
                2XXXX - 处理失败
            msg : 处理状态对应的描述
            session_id : 返回的session id
        """
        # 创建session并存入信息
        _qa: QA = RunTool.get_global_var('QA_LOADER').qa
        try:
            _session_id = _qa.generate_session(request.json)
            _ret_json = {
                'status': '00000',
                'msg': 'success',
                'session_id': _session_id
            }
        except:
            _ret_json = {
                'status': '20001',
                'msg': '生成session id出现异常'
            }

        # 返回结果
        return jsonify(_ret_json)

    @classmethod
    @FlaskTool.log
    def SearchAnswer(cls, methods=['POST']):
        """
        获取问题答案
        传入信息为json字典，定义如下:
            {
                'session_id': GetSessionId获取的session id,
                'question': 客户的输入,
                'collection': 指定的问题分类，可不传
            }

        @return {str} - 返回回答的json字符串
            status : 处理状态
                00000 - 成功, 返回一条回答
                00001 - 成功, 返回上下文选择清单
                10000 - 未匹配到任何回答, 会获取默认回答
                10001 - session id为必填
                10002 - session id不存在或已失效
                2XXXX - 处理失败
            msg : 处理状态对应的描述
            answers : 匹配答案数组
        """
        try:
            print(request.json)
            _qa: QA = RunTool.get_global_var('QA_LOADER').qa
            _ret_json = {
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

            _answers = _qa.quession_search(_question, _session_id, _collection)

            if len(_answers) > 1:
                _ret_json['status'] = '00001'

            _ret_json['answers'] = _answers
        except FileNotFoundError:
            _ret_json = {
                'status': '10002',
                'msg': 'session id 不存在'
            }
        except:
            print(traceback.format_exc())
            _ret_json = {
                'status': '20001',
                'msg': '获取答案出现异常'
            }
        print(_ret_json)
        return jsonify(_ret_json)


class QaDataManager(object):
    """
    QA问题答案管理对外提供的restful api服务类
    规则如下：
        1、每个非'_'开头的静态函数为一个对外API服务；
        2、可以通过函数最后的methods参数指定api的动作，例如指定GET、POST等，例如['GET']、['GET', 'POST']
        3、可以通过函数最后的ver参数指定api支持版本号，注意需要设置当调用不传入版本号时的默认值
        3、函数的入参定义会反映到路由中（methods/ver参数除外）
    例如：
        Test(a:str, b:int, methods=['GET'], ver='0.5')会自动配置路由为：
            Rule('/api/<ver>/ClassName/Test/<a>/<int:b>', endpoint='ClassName.Test', methods=['GET'])
            Rule('/api/ClassName/Test/<a>/<int:b>', endpoint='ClassName.Test', methods=['GET'])
        Test(a:str, b:int, methods=['GET'])会自动配置路由为：
            Rule('/api/ClassName/Test/<a>/<int:b>', endpoint='ClassName.Test', methods=['GET'])
    函数内部可以使用以下方法获取传入参数：
        1、通过request.args['key']，获取'?key=value&key1=value1'这类的传参
        2、通过request.json['key']，获取在body传入的json结构对应的key的值，例如
            request.json['id']可以获取body中的“{"id": 1234, "info": "测试\\n一下"}” 的id的值
            注意：报文头的Content-Type必须为application/json
        3、通过request.files['file']，获取上传的文件
    函数可以通过jsonify将python对象转换为json字符串返回到请求端

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
