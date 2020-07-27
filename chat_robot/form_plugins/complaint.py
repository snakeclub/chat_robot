#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
表单插件实例 - 投诉
@module complaint
@file complaint.py
"""

import os
import sys
import traceback
import datetime
from flask import request, jsonify
from HiveNetLib.base_tools.run_tool import RunTool
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.qa import QA
from chat_robot.lib.data_manager import QAManager
from chat_robot.lib.restful_api import FlaskTool
from chat_robot.ext_plugins.form import FormPluginApi, FormPlugin


__MOUDLE__ = 'complaint'  # 模块名
__DESCRIPT__ = u'表单插件实例 - 投诉'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.07.25'  # 发布日期


class ComplaintFormServer(object):
    """
    投诉表单的接口服务
    """

    @classmethod
    @FlaskTool.log
    @FlaskTool.db_connect
    def RespMsg(cls, methods=['POST']):
        """
        将发向客户的消息放入客户待发送消息队列
        传入信息为json字典，例如:
            {
                'interface_seq_id': '(可选)客户端序号，客户端可传入该值来支持异步调用'
                'user_name': 'API用户的登陆用户名（非客户用户）, 如果验证方式是密码形式提供',
                'password': 'API用户的登陆密码（非客户用户）, 如果验证方式是密码形式提供',
                'form_id': XX,  # 表单id
                'resp_msg': '', # 回复内容
                'upd_status': '', # 更新的表单状态 untreated / treating / treated / canceled
                'from_user_id': xx,  消息发起用户id，可以填0
                'from_user_name': '系统',
            }

        @return {str} - 返回回答的json字符串
            interface_seq_id : 回传客户端的接口请求id
            status : 处理状态
                00000 - 处理成功
                10001 - 用户名密码验证失败
                10002 - 访问IP验证失败
                2XXXX - 处理失败
            msg : 处理状态对应的描述
        """
        _qa_loader = RunTool.get_global_var('QA_LOADER')
        _interface_seq_id = ''
        try:
            if hasattr(request, 'json') and request.json is not None:
                _interface_seq_id = request.json.get('interface_seq_id', '')

            _ret_json = {
                'interface_seq_id': _interface_seq_id,
                'status': '00000',
                'msg': 'success',
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
                    request.json['user_name'],
                    request.json['password'],
                    is_generate_token=False
                )

                _ret_json['status'] = _back['status']
                if _back['status'] != '00000':
                    if _back['status'] == '10001':
                        _ret_json['msg'] = 'user_name not exists!'
                    else:
                        _ret_json['msg'] = 'user_name or password error!'

            # 处理消息添加
            if _back['status'] == '00000':
                # 获取投诉信息数据库对象
                op_para = {
                    'form_type': ComplaintForm.get_form_type(),
                    'form_id': request.json['form_id']
                }

                _form_obj = FormPluginApi.get_form_obj(
                    op_para, '', _qa_loader.qa, _qa_loader.qa_manager
                )

                if _form_obj is None:
                    _ret_json['status'] = '10003'
                    _ret_json['msg'] = '表单不存在！'
                else:
                    # 更新投诉回复信息
                    _upd_time = datetime.datetime.now()

                    # 处理回复消息更新
                    _resp_msg = request.json.get('resp_msg', None)
                    if _resp_msg is not None:
                        _data_dict = eval(str(_form_obj.data, encoding='utf-8'))
                        if 'response' not in _data_dict.keys():
                            _data_dict['response'] = list()

                        _data_dict['response'].append({
                            'from_user_id': request.json.get('from_user_id', 0),
                            'from_user_name': request.json.get('from_user_name', '系统'),
                            'resp_time': _upd_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'resp_msg': _resp_msg
                        })

                        op_para['data'] = _data_dict

                    # 处理状态的更新
                    if 'upd_status' in request.json.keys():
                        op_para['status'] = request.json['upd_status']

                    # 保存记录
                    _form_obj = FormPluginApi.upd_form(
                        op_para, '', _qa_loader.qa, _qa_loader.qa_manager
                    )

                    # 放入给客户的提示信息中
                    _form_info = FormPluginApi.get_form_preview_dict(_form_obj)
                    _qa_loader.qa.add_send_message(
                        _form_obj.user_id, _form_info,
                        from_user_id=request.json.get('from_user_id', 0),
                        from_user_name=request.json.get('from_user_name', '系统'),
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
                'msg': '回复投诉异常'
            }

        # 返回结果
        return jsonify(_ret_json)


class ComplaintForm(object):
    """
    投诉表单实例配置
    """

    @classmethod
    def get_form_type(cls) -> str:
        """
        返回表单类型(必须实现)

        @returns {str} - 表单类型
        """
        return 'complaint'

    @classmethod
    def get_form_config(cls) -> dict:
        """
        返回表单配置字典(必须实现)

        @returns {dict} - 表单配置字典
        """
        return {
            # 投诉的表单配置
            'name': '投诉',
            # 要执行的初始化函数, 入参跟插件的初始化函数一致(loader, qa_manager, qa, **kwargs), 无需执行传入None
            'initialize_fun': cls._initialize_fun,  # 初始化函数
            'data_table': '',  # 存储表单数据的表对象，如果为str代表自定义的表名，如果为''代表使用默认表存储，否则为BaseModel对象
            'default_fun': cls._complaint_get_default,  # 获取表单默认值字典的函数，不设置默认值传None，函数定义参考：cls._complaint_get_default
            'op_predeal_fun': cls._complaint_op_predeal,  # 表单操作预处理函数，函数定义参考：cls._complaint_op_predeal
            # 生成表单预览字典的函数，函数定义参考：cls._complaint_generate_preview
            'generate_preview_fun': cls._complaint_generate_preview,
            'saved_tips': None,  # 表单保存后的提示信息{str}，如果为None代表返回预览信息字典
            'upd_tips': '亲, 投诉信息已完成更新',  # 表单更新后的提示信息，如果为None代表返回预览信息字典
            'answer_with_def': False,  # 问题回答是否包含表单字段定义
            # 预览字段定义, key-字段标识, value-字段定义数组 [中文名, 类型, 顺序, 取值范围]
            'preview_def': {},
            # 表单字段定义, key-字段标识, value-字段定义数组 [中文名, 类型, 顺序, 取值范围]
            'form_def': {},
            # NLP意图匹配配置
            'order_num': 100,  # 匹配顺序
            'exact_match_words': ['投诉', '我要投诉', '我想投诉', '我想要投诉'],  # 精确指令
            'exact_ignorecase': 'N',  # 忽略大小写
            'match_words': ['投诉', '我要投诉', '我想投诉', '我想要投诉'],  # 分词模式匹配
            'ignorecase': 'N',  # 是否忽略大小写
            'word_scale': 0,  # 分词模式必须超过2/3比例
            'info': [],  # 获取方法配置
            'check': ['InitCheck', 'check_by_position', {'postion': 'start'}],  # 检查方法配置
        }

    #############################
    # 内部函数
    #############################
    @classmethod
    def _initialize_fun(cls, loader, qa_manager, qa, **kwargs):
        """
        插件初始化操作

        @param {QAServerLoader} loader - 服务装载器
        @param {QAManager} qa_manager - 数据管理
        @param {QA} qa - 问答服务
        """
        # 将回复投诉功能服务加入Restful Api服务
        loader.api_class.append(ComplaintFormServer)

    @classmethod
    def _complaint_op_predeal(cls, op_para: dict, question: str, session_id: str,
                              qa: QA, qa_manager: QAManager, **kwargs):
        """
        留言的表单操作预处理函数

        @param {dict} op_para - 上送的表单操作参数
        @param {str} question - 原始问题
        @param {str} session_id - session_id
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 扩展传入参数

        @returns {str, object} - 返回控制处理的参数: action, action_para
            action取值的类型和对应的行为如下：
            'answer', [str, ...]  - 直接返回回复内容，第二个参数为回复内容
            'to', int - 跳转到指定问题处理，第二个参数为std_question_id
            'save', None - 根据op_para参数保存表单
            'upd', None - 根据op_para参数更新表单
            'preview', None - 获取表单预览信息
            'get', None - 获取表单完整信息
            'create', None - 创建表单
        """
        # 检查用户是否已登陆
        if qa.get_info_by_key(session_id, 'user_id', -1) == -1:
            return 'answer', ['亲, 投诉需要先登陆哦', ]

        # 不改变操作模式
        return op_para['action'], None

    @classmethod
    def _complaint_get_default(cls, question: str, session_id: str,
                               qa: QA, qa_manager: QAManager, **kwargs) -> dict:
        """
        投诉表单默认值字典的函数

        @param {str} question - 原始问题
        @param {str} session_id - session_id
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 扩展传入参数

        @returns {dict} - 返回的默认值字典
        """
        _dict = {
            'user_id': qa.get_info_by_key(session_id, 'user_id', -1),
            'user_name': qa.get_info_by_key(session_id, 'user_name', ''),
        }
        if question not in ['投诉', '我要投诉']:
            _dict['content'] = question

        return _dict

    @classmethod
    def _complaint_generate_preview(cls, form_type: str, form_data: dict) -> dict:
        """
        创建留言的预览字典信息

        @param {str} form_type - 表单类型
        @param {dict} form_data - 要保存的字典信息

        @returns {dict} - 返回的预览字典信息
        """
        _len = 10
        _content = form_data['content']
        _preview = {
            'content': '%s...' % _content[0:_len] if len(_content) > _len else _content,
        }
        return _preview


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))
