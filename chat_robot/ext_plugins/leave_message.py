#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
留言插件
@module leave_message
@file leave_message.py
"""

import os
import sys
import datetime
import traceback
from flask import request, jsonify
from HiveNetLib.base_tools.run_tool import RunTool
import peewee as pw
from HiveNetLib.base_tools.file_tool import FileTool
from HiveNetLib.simple_log import Logger
from HiveNetLib.simple_xml import SimpleXml
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.answer_db import BaseModel, AnswerDao, StdQuestion, Answer, NlpPurposConfigDict, UploadFileConfig
from chat_robot.lib.qa import QA
from chat_robot.lib.data_manager import QAManager
from chat_robot.lib.restful_api import FlaskTool


__MOUDLE__ = 'leave_message'  # 模块名
__DESCRIPT__ = u'留言插件'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.07.26'  # 发布日期


#############################
# 数据库表
#############################
class LeaveMessagePluginData(BaseModel):
    """
    留言数据表
    """
    id = pw.BigAutoField()  # 留言id
    ref_id = pw.BigIntegerField(default=-1)  # 关联留言id（一个对话下来的留言id, 取第一个留言的id）
    user_id = pw.BigIntegerField(index=True)  # 留言所属客户id
    user_name = pw.CharField(max_length=50)  # 留言用户名
    status = pw.CharField(
        max_length=20,
        choices=[('untreated', '未处理'), ('treating', '处理中'),
                 ('treated', '已处理'), ('canceled', '已撤销')],
        default='untreated', index=True
    )  # 处理状态
    msg = pw.CharField(max_length=2000)  # 客户留言信息
    pic_urls = pw.CharField(max_length=1000, default='')  # 客户上传的图片文件url清单, 逗号分隔
    ref_msg = pw.CharField(max_length=2000, default='')  # 留言引用对话消息内容
    resp_time = pw.DateTimeField(null=True)  # 回复时间
    resp_user_id = pw.BigIntegerField(index=True, default=0)  # 回复用户id
    resp_user_name = pw.CharField(default='')  # 回复用户名
    resp_msg = pw.CharField(max_length=2000, default='')  # 回复信息
    resp_pic_urls = pw.CharField(max_length=1000, default='')  # 回复的图片文件url清单, 逗号分隔
    create_time = pw.DateTimeField(default=datetime.datetime.now)  # 创建时间

    class Meta:
        # 定义数据库表名
        table_name = 'leave_message_plugin_data'


#############################
# 留言插件配置
#############################
# 上传文件配置
LEAVE_MESSAGE_PLUGIN_UPLOAD_FILE_CONFIG = {
    'upload_type': 'leave_message_file',
    'exts': "['jpg', 'jpeg', 'png', 'gif']",
    'size': 0,
    'save_path': './client/static/leave_message',
    'url': '/static/leave_message/',
    'rename': 'leave_message_{$datetime=%Y%m%d%H%M%S$}.{$file_ext=$}',
    'after': "['InitUploadAfter', 'generate_thumbnail', {}]",
    'remark': '留言插件文件上传'
}

LEAVE_MESSAGE_PLUGIN_COLLECTION = 'chat'  # 所在问题分类
LEAVE_MESSAGE_PLUGIN_PARTITION = ''  # 所在问题场景
LEAVE_MESSAGE_PLUGIN_REF_MSG_LEN = 20  # 引用信息长度
# 提示信息
LEAVE_MESSAGE_PLUGIN_TIPS = {
    'start_tips': '亲, 请通过回复方式留下您的留言, 回复前您也可以通过上传按钮上传本次留言的图片',
    'upload_success': '留言附件上传成功',
    'success': '亲, 您的留言已提交后台工作人员, 我们将尽快处理并回复您',
    'cancle': '亲, 已取消留言处理',
    'context_error': '亲, 该操作已结束，如果您想发起新的留言，可直接回复 "留言"',
}
# 留言意图匹配参数
LEAVE_MESSAGE_PLUGIN_NLP_CONFIG = {
    'order_num': 100,  # 匹配顺序
    'exact_match_words': ['留言', '我要留言', '我想留言', '我想要留言'],  # 精确指令
    'exact_ignorecase': 'N',  # 忽略大小写
    'match_words': ['留言', '我要留言', '我想留言', '我想要留言'],  # 分词模式匹配
    'ignorecase': 'N',  # 是否忽略大小写
    'word_scale': 0,  # 分词模式必须超过2/3比例
    'info': [],  # 获取方法配置
    'check': ['InitCheck', 'check_by_position', {'postion': 'start'}],  # 检查方法配置
}


#############################
# 数据初始化处理工具
#############################
DATA_TABLES = [LeaveMessagePluginData]  # 数据表


class InitDataTool(object):
    """
    数据初始化处理工具
    """

    @classmethod
    def get_init_objs(cls) -> dict:
        """
        获取工具初始化对象

        @returns {dict} - 初始化对象
        """
        # 获取配置文件信息
        _execute_path = os.path.realpath(FileTool.get_file_path(__file__))
        _config = os.path.join(_execute_path, '../conf/server.xml')

        _config_xml = SimpleXml(_config, encoding='utf-8')
        _server_config = _config_xml.to_dict()['server']

        # 日志对象
        _logger: Logger = None
        if 'logger' in _server_config.keys():
            _logger = Logger.create_logger_by_dict(_server_config['logger'])

        # 连接数据库操作对象
        _qa_manager = QAManager(
            _server_config['answerdb'], _server_config['milvus'], _server_config['bert_client'],
            logger=_logger, excel_batch_num=_server_config['excel_batch_num'],
            excel_engine=_server_config['excel_engine'], load_para=False
        )

        return {
            'logger': _logger,
            'qa_manager': _qa_manager
        }

    @classmethod
    def remove_data(cls, qa_manager: QAManager, logger: Logger):
        """
        清空所有数据

        @param {QAManager} qa_manager - 数据管理对象
        @param {Logger} logger - 日志对象
        """
        AnswerDao.drop_tables(DATA_TABLES)
        AnswerDao.create_tables(DATA_TABLES)

        # 删除上传文件
        _execute_path = os.path.realpath(FileTool.get_file_path(__file__))
        FileTool.remove_all_with_path(
            path=os.path.join(_execute_path, '../client/static/leave_message')
        )

        if logger is not None:
            logger.debug('remove leave message plugin data success!')

    @classmethod
    def remove_config(cls, qa_manager: QAManager, logger: Logger):
        """
        清空所有配置

        @param {QAManager} qa_manager - 数据管理对象
        @param {Logger} logger - 日志对象
        """
        # 意图配置
        _ret = NlpPurposConfigDict.delete().where(NlpPurposConfigDict.action == 'leave_message').execute()
        if logger is not None:
            logger.debug('remove leave message plugin nlp config success: %s !' % str(_ret))

        # 文件上传参数
        _ret = UploadFileConfig.delete().where(
            UploadFileConfig.upload_type == LEAVE_MESSAGE_PLUGIN_UPLOAD_FILE_CONFIG['upload_type']
        ).execute()
        if logger is not None:
            logger.debug('remove leave message plugin file upload config success: %s !' % str(_ret))

        # 标准问题和答案
        _std_q = StdQuestion.get_or_none(StdQuestion.tag == 'leave_message_direct_action')
        if _std_q is not None:
            _ret = Answer.delete().where(
                Answer.std_question_id == _std_q.id
            ).execute()
            _ret = StdQuestion.delete().where(StdQuestion.id == _std_q.id).execute()
            if logger is not None:
                logger.debug(
                    'remove leave message plugin std question config success: %s !' % str(_ret))

    @classmethod
    def import_config(cls, qa_manager: QAManager, logger: Logger):
        """
        添加标准配置(不考虑删除问题)

        @param {QAManager} qa_manager - 数据管理对象
        @param {Logger} logger - 日志对象
        """
        # 插入标准问题
        _std_q = StdQuestion.create(
            tag='leave_message_direct_action',
            q_type='context', milvus_id=-1, collection=LEAVE_MESSAGE_PLUGIN_COLLECTION,
            partition=LEAVE_MESSAGE_PLUGIN_PARTITION,
            question='留言插件通用处理'
        )

        # 插入问题答案
        Answer.create(
            std_question_id=_std_q.id, a_type='ask',
            type_param="['LeaveMessagePlugin', 'save_msg', '', '', {}, True]",
            replace_pre_def='N',
            answer='留言插件通用处理'
        )

        if logger is not None:
            logger.info('create leave message plugin std question config success!')

        # 创建留言意图参数
        NlpPurposConfigDict.create(
            action='leave_message',
            match_collection='', match_partition='',
            collection=LEAVE_MESSAGE_PLUGIN_COLLECTION,
            partition=LEAVE_MESSAGE_PLUGIN_PARTITION,
            std_question_id=_std_q.id,
            order_num=LEAVE_MESSAGE_PLUGIN_NLP_CONFIG['order_num'],
            exact_match_words=str(LEAVE_MESSAGE_PLUGIN_NLP_CONFIG['exact_match_words']),
            exact_ignorecase=LEAVE_MESSAGE_PLUGIN_NLP_CONFIG['exact_ignorecase'],
            match_words=str(LEAVE_MESSAGE_PLUGIN_NLP_CONFIG['match_words']),
            ignorecase=LEAVE_MESSAGE_PLUGIN_NLP_CONFIG['ignorecase'],
            word_scale=LEAVE_MESSAGE_PLUGIN_NLP_CONFIG['word_scale'],
            info=str(LEAVE_MESSAGE_PLUGIN_NLP_CONFIG['info']),
            check=str(LEAVE_MESSAGE_PLUGIN_NLP_CONFIG['check'])
        )
        if logger is not None:
            logger.info('create leave message plugin nlp config success!')

        # 创建文件上传参数
        UploadFileConfig.create(
            upload_type=LEAVE_MESSAGE_PLUGIN_UPLOAD_FILE_CONFIG['upload_type'],
            exts=LEAVE_MESSAGE_PLUGIN_UPLOAD_FILE_CONFIG['exts'],
            size=LEAVE_MESSAGE_PLUGIN_UPLOAD_FILE_CONFIG['size'],
            save_path=LEAVE_MESSAGE_PLUGIN_UPLOAD_FILE_CONFIG['save_path'],
            url=LEAVE_MESSAGE_PLUGIN_UPLOAD_FILE_CONFIG['url'],
            rename=LEAVE_MESSAGE_PLUGIN_UPLOAD_FILE_CONFIG['rename'],
            after=LEAVE_MESSAGE_PLUGIN_UPLOAD_FILE_CONFIG['after'],
            remark=LEAVE_MESSAGE_PLUGIN_UPLOAD_FILE_CONFIG['remark']
        )

        if logger is not None:
            logger.info('create leave message plugin upload file config success!')


#############################
# 服务端处理留言的API
#############################
class LeaveMessagePluginServer(object):
    """
    留言的服务端接口
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
                'msg_id': XX,  # 留言id
                'resp_msg': '', # 回复内容
                'resp_pic_urls': '', # 回复图片url清单，用逗号分隔
                'upd_status': '', # 更新留言处理状态 untreated / treating / treated / canceled
                'resp_user_id': xx,  处理用户id，可以填0
                'resp_user_name': '系统',  处理用户名
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
                # 获取留言信息数据库对象
                _msg_obj = LeaveMessagePluginData.get_or_none(
                    LeaveMessagePluginData.id == request.json['msg_id']
                )

                if _msg_obj is None:
                    _ret_json['status'] = '10003'
                    _ret_json['msg'] = '留言不存在！'
                else:
                    # 更新留言回复信息
                    _msg_obj.resp_time = datetime.datetime.now()
                    _msg_obj.resp_msg = request.json.get('resp_msg')
                    _msg_obj.resp_pic_urls = request.json.get('resp_pic_urls', '')
                    _msg_obj.resp_user_id = request.json.get('resp_user_id', 0)
                    _msg_obj.resp_user_name = request.json.get('resp_user_name', '系统')
                    # 处理状态的更新
                    if 'upd_status' in request.json.keys():
                        _msg_obj.status = request.json['upd_status']

                    # 保存记录
                    _msg_obj.save()

                    # 放入给客户的提示信息中
                    _send_info = {
                        'data_type': 'leave_message',
                        'action': 'resp',
                        'tips': _msg_obj.resp_msg,
                        'msg_id': _msg_obj.id,
                        'msg': _msg_obj.msg if len(_msg_obj.msg) <= LEAVE_MESSAGE_PLUGIN_REF_MSG_LEN else _msg_obj.msg[0:LEAVE_MESSAGE_PLUGIN_REF_MSG_LEN] + '...',
                        'resp_pic_urls': _msg_obj.resp_pic_urls.split(',')
                    }
                    _qa_loader.qa.add_send_message(
                        _msg_obj.user_id, _send_info,
                        from_user_id=_msg_obj.resp_user_id,
                        from_user_name=_msg_obj.resp_user_name,
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
                'msg': '回复留言异常'
            }

        # 返回结果
        return jsonify(_ret_json)


#############################
# 留言问题插件
#############################
class LeaveMessagePlugin(object):
    """
    留言插件
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
        # 将回复留言功能服务加入Restful Api服务
        loader.api_class.append(LeaveMessagePluginServer)

    @classmethod
    def save_msg(cls, question: str, session_id: str, context_id: str, std_question_id: int,
                 collection: str, partition: str,
                 qa: QA, qa_manager: QAManager, **kwargs):
        """
        保存留言信息

        @param {str} question - 客户反馈的信息文本(提问回答)
        @param {str} session_id - 客户的session id
        @param {str} context_id - 上下文临时id
        @param {int} std_question_id - 上下文中对应的提问问题id
        @param {str} collection - 提问答案参数指定的问题分类
        @param {str} partition - 提问答案参数指定的场景标签
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 扩展传入参数

        @returns {str, object} - 按照不同的处理要求返回内容
            'answer', [str, ...]  - 直接返回回复内容，第二个参数为回复内容
            'to', int - 跳转到指定问题处理，第二个参数为std_question_id
            'again', [str, ...] - 再获取一次答案，第二个参数为提示内容，如果第2个参数为None代表使用原来的参数再提问一次
            'break', [collection, partition] - 跳出问题(让问题继续走匹配流程)，可以返回[collection, partition]变更分类和场景
            默认为'again'
        """
        _context_dict = qa.get_context_dict(session_id)
        if 'leave_message' not in _context_dict['ask'].keys():
            # 第一次进入留言模块
            _leave_message = {
                'context_id': context_id,  # 临时会话id
                'ref_id': -1,
                'ref_msg': '',
                'pic_urls': [],
            }
            if 'action' in kwargs.keys():
                # 操作意图发起，属于客户聊天发起的留言
                if kwargs['match_type'] == 'nlp_match' and len(question) > len(kwargs['match_word']) + 4:
                    # 分词模式并且留言后面有内容，可以直接保存
                    _leave_message['msg'] = question
            else:
                # 直接发起的留言，可以传入引用信息
                _ref_info = eval(question)
                _ref_id = _ref_info.get('ref_id', -1)
                if _ref_id != -1:
                    _ref_data = LeaveMessagePluginData.get_or_none(
                        LeaveMessagePluginData.id == _ref_id)
                    if _ref_data is not None and _ref_data.ref_id != -1:
                        _ref_id = _ref_data.ref_id

                _leave_message['ref_id'] = _ref_id
                _leave_message['ref_msg'] = _ref_info.get('ref_msg', '')
        else:
            # 第二次进入留言模块，检查是否上传图片的记录
            _leave_message = _context_dict['ask']['leave_message']
            try:
                _op_para = eval(question)
                _context_id = _op_para.get('context_id', '')
                if _context_id != context_id:
                    # 非本次会话的留言
                    return 'answer', [LEAVE_MESSAGE_PLUGIN_TIPS['context_error']]

                if 'action' in _op_para.keys():
                    if _op_para['action'] == 'upload_file':
                        _leave_message['pic_urls'].append(_op_para['url'])
                    elif _op_para['action'] == 'cancle':
                        # 取消留言
                        return 'answer', [{
                            'data_type': 'leave_message',
                            'tips': LEAVE_MESSAGE_PLUGIN_TIPS['cancle'],
                            'action': 'cancle',
                            'context_id': context_id
                        }]
                    else:
                        _leave_message['msg'] = question
                else:
                    _leave_message['msg'] = question
            except:
                _leave_message['msg'] = question

        if 'msg' not in _leave_message.keys():
            # 第一次处理，保存问题缓存并提示客户回复留言
            _context_dict['ask']['leave_message'] = _leave_message
            qa.add_ask_context(session_id, _context_dict['ask'])
            if len(_leave_message['pic_urls']) > 0:
                return 'again', [LEAVE_MESSAGE_PLUGIN_TIPS['upload_success'], ]
            else:
                return 'again', [{
                    'data_type': 'leave_message',
                    'tips': LEAVE_MESSAGE_PLUGIN_TIPS['start_tips'],
                    'action': 'add',
                    'context_id': context_id
                }]
        else:
            # 保存留言
            _data = LeaveMessagePluginData.create(
                ref_id=_leave_message['ref_id'],
                user_id=qa.get_info_by_key(session_id, 'user_id', default=-1),
                user_name=qa.get_info_by_key(session_id, 'user_name', ''),
                msg=_leave_message['msg'],
                ref_msg=_leave_message['ref_msg'],
                pic_urls=','.join(_leave_message['pic_urls']),
            )

            # 返回客户提示
            return 'answer', [{
                'data_type': 'leave_message',
                'tips': LEAVE_MESSAGE_PLUGIN_TIPS['success'],
                'action': 'success',
                'context_id': context_id,
                'msg_id': _data.id,
            }]


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))

    # 命令方式：python leave_message.py op=reset type=all
    _opts = RunTool.get_kv_opts()
    if 'op' in _opts.keys():
        # 需要执行操作
        _op = _opts['op']
        _init_objs = InitDataTool.get_init_objs()
        if _op == 'reset':
            _set_type = _opts.get('type', 'config')
            if _set_type == 'config':
                InitDataTool.remove_config(_init_objs['qa_manager'], _init_objs['logger'])
                InitDataTool.import_config(_init_objs['qa_manager'], _init_objs['logger'])
            elif _set_type == 'data':
                InitDataTool.remove_data(_init_objs['qa_manager'], _init_objs['logger'])
            elif _set_type == 'all':
                InitDataTool.remove_data(_init_objs['qa_manager'], _init_objs['logger'])
                InitDataTool.remove_config(_init_objs['qa_manager'], _init_objs['logger'])
                InitDataTool.import_config(_init_objs['qa_manager'], _init_objs['logger'])
