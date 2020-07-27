#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
表单插件
@module form
@file form.py
"""

import os
import sys
import datetime
import inspect
import peewee as pw
from HiveNetLib.base_tools.file_tool import FileTool
from HiveNetLib.base_tools.import_tool import ImportTool
from HiveNetLib.base_tools.run_tool import RunTool
from HiveNetLib.simple_log import Logger
from HiveNetLib.simple_xml import SimpleXml
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.answer_db import BaseModel, AnswerDao, StdQuestion, Answer, NlpPurposConfigDict
from chat_robot.lib.qa import QA
from chat_robot.lib.data_manager import QAManager


__MOUDLE__ = 'form'  # 模块名
__DESCRIPT__ = u'表单插件'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.07.20'  # 发布日期


#############################
# 数据库
#############################
class FormPluginData(BaseModel):
    """
    通用表单数据存储(如果自定义表，也需跟该表结构一致)
    """
    id = pw.BigAutoField()  # 表单id
    form_type = pw.CharField(max_length=50, index=True)  # 表单类型标识
    user_id = pw.BigIntegerField(index=True)  # 表单所属客户id
    user_name = pw.CharField(max_length=50)  # 表单用户名
    status = pw.CharField(
        max_length=20,
        choices=[('untreated', '未处理'), ('treating', '处理中'),
                 ('treated', '已处理'), ('canceled', '已撤销')],
        default='untreated', index=True
    )  # 处理状态
    preview = pw.CharField(max_length=4000)  # 预览，json字符串格式，data的一部分内容，用于预览显示
    data = pw.BlobField()  # 表单详细数据, json字符串的格式转为二进制存储
    last_upd_time = pw.DateTimeField(default=datetime.datetime.now)  # 最后更新时间
    create_time = pw.DateTimeField(default=datetime.datetime.now)  # 创建时间

    class Meta:
        # 定义数据库表名
        table_name = 'form_plugin_data'


#############################
# 表单处理类
#############################
FORM_PLUGIN_TIPS = {
    # 表单提示信息配置
    'unsupport_form_type': '抱歉, 亲, 暂时未能理解您的问题',
    'unsupport_form_action': '亲, 该表单不支持对应的操作',
    'form_not_exists': '亲，该表单不存在',
}

FORM_PLUGIN_COLLECTION = 'chat'  # 表单插件的分类集, 需注意修改
FORM_PLUGIN_PARTITION = ''  # 表单插件的特殊场景
FORM_PLUGIN_SEARCH_PATH = '../form_plugins'  # 获取表单插件实例的库文件目录, 如果不需要装载插件实例置为None


class FormPluginApi(object):
    """
    表单操作Api
    """

    @classmethod
    def save_form(cls, op_para: dict, session_id: str, qa: QA, qa_manager: QAManager):
        """
        保存表单数据

        @param {dict} op_para - 操作参数字典，定义如下：
            data_type {str} - 数据类型，默认为'form'
            form_type {str} - 表单类型
            name {str} - 表单名
            user_id {int} - 用户id
            user_name {str} - 用户名
            data {dict} - 表单数据字典
        @param {str} session_id - session_id
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象

        @returns {BaseModel} - 返回保存的数据库记录对象
        """
        FORM_PLUGIN_CONFIG = RunTool.get_global_var('FORM_PLUGIN_CONFIG')
        _form_config = FORM_PLUGIN_CONFIG[op_para['form_type']]
        _preview = dict()
        if 'generate_preview_fun' in _form_config.keys():
            _generate_preview_fun = _form_config['generate_preview_fun']
            if _generate_preview_fun is not None:
                _preview = _generate_preview_fun(op_para['form_type'], op_para['data'])

        # 获取表对象
        _table_obj = cls._get_table_obj(_form_config.get('data_table', ''))

        # 保存数据
        _save_obj = _table_obj.create(
            form_type=op_para['form_type'],
            user_id=op_para['user_id'],
            user_name=op_para['user_name'],
            preview=str(_preview),
            data=bytes(str(op_para['data']), encoding='utf-8')
        )
        return _save_obj

    @classmethod
    def upd_form(cls, op_para: dict, session_id: str, qa: QA, qa_manager: QAManager):
        """
        更新表单数据

        @param {dict} op_para - 操作参数字典，定义如下：
            data_type {str} - 数据类型，默认为'form'
            form_type {str} - 表单类型
            form_id {int} - 要更新的表单id
            其他只传需要更新的表单字段即可，支持修改：status,
        @param {str} session_id - session_id
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象

        @returns {BaseModel} - 返回更新后的数据库记录对象
        """
        FORM_PLUGIN_CONFIG = RunTool.get_global_var('FORM_PLUGIN_CONFIG')
        _form_config = FORM_PLUGIN_CONFIG[op_para['form_type']]
        _table_obj = cls._get_table_obj(_form_config.get('data_table', ''))

        # 修改记录
        _form_obj = _table_obj.get_or_none(_table_obj.id == op_para['form_id'])
        if _form_obj is not None:
            if 'status' in op_para.keys():
                _form_obj.status = op_para['status']

            if 'data' in op_para.keys():
                _preview = dict()
                if 'generate_preview_fun' in _form_config.keys():
                    _generate_preview_fun = _form_config['generate_preview_fun']
                    if _generate_preview_fun is not None:
                        _preview = _generate_preview_fun(op_para['form_type'], op_para['data'])

                _form_obj.preview = str(_preview)
                _form_obj.data = bytes(str(op_para['data']), encoding='utf-8')

            # 最后更新时间
            _form_obj.last_upd_time = datetime.datetime.now()

            # 执行保存操作
            _form_obj.save()

        return _form_obj

    @classmethod
    def get_form_obj(cls, op_para: dict, session_id: str, qa: QA, qa_manager: QAManager):
        """
        获取表单数据

        @param {dict} op_para - 操作参数字典，定义如下：
            data_type {str} - 数据类型，默认为'form'
            form_type {str} - 表单类型
            form_id {int} - 要更新的表单id
            其他只传需要更新的表单字段即可，支持修改：status,
        @param {str} session_id - session_id
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象

        @returns {BaseModel} - 返回数据库记录对象
        """
        FORM_PLUGIN_CONFIG = RunTool.get_global_var('FORM_PLUGIN_CONFIG')
        _form_config = FORM_PLUGIN_CONFIG[op_para['form_type']]
        _table_obj = cls._get_table_obj(_form_config.get('data_table', ''))

        return _table_obj.get_or_none(_table_obj.id == op_para['form_id'])

    @classmethod
    def get_form_preview_dict(cls, form_obj, std_question_id: int = -1) -> dict:
        """
        获取表单预览字典

        @param {Model} form_obj - 表单数据库记录对象

        @returns {dict} - 返回预览字典
        """
        FORM_PLUGIN_CONFIG = RunTool.get_global_var('FORM_PLUGIN_CONFIG')
        _form_config = FORM_PLUGIN_CONFIG[form_obj.form_type]
        _form_info = {
            'data_type': 'form',
            'action': 'preview',
            'std_question_id': std_question_id,
            'form_type': form_obj.form_type,
            'name': _form_config['name'],
        }

        cls.update_form_preview_dict(form_obj, _form_info)

        if _form_config['answer_with_def']:
            _form_info['preview_def'] = _form_config['preview_def']

        return _form_info

    @classmethod
    def get_form_info_dict(cls, form_obj, std_question_id: int = -1) -> dict:
        """
        获取表单详细信息字典

        @param {Model} form_obj - 表单数据库记录对象

        @returns {dict} - 返回详细信息字典
        """
        FORM_PLUGIN_CONFIG = RunTool.get_global_var('FORM_PLUGIN_CONFIG')
        _form_config = FORM_PLUGIN_CONFIG[form_obj.form_type]
        _form_info = {
            'data_type': 'form',
            'action': 'detail',
            'std_question_id': std_question_id,
            'form_type': form_obj.form_type,
            'name': _form_config['name'],
        }
        cls.update_form_data_dict(form_obj, _form_info)

        if _form_config['answer_with_def']:
            _form_info['form_def'] = _form_config['form_def']

        return _form_info

    @classmethod
    def update_form_preview_dict(cls, form_obj, info_dict: dict):
        """
        通过记录对象更新信息字典

        @param {Model} form_obj - 表单记录对象
        @param {dict} info_dict - 要更新的信息字典
        """
        info_dict.update({
            'form_id': form_obj.id,
            'user_id': form_obj.user_id,
            'status': form_obj.status,
            'preview': eval(form_obj.preview),
            'last_upd_time': form_obj.last_upd_time.strftime('%Y-%m-%d %H:%M:%S'),
            'create_time': form_obj.create_time.strftime('%Y-%m-%d %H:%M:%S'),
        })

    @classmethod
    def update_form_data_dict(cls, form_obj, info_dict: dict):
        """
        通过记录对象更新信息字典

        @param {Model} form_obj - 表单记录对象
        @param {dict} info_dict - 要更新的信息字典
        """
        info_dict.update({
            'form_id': form_obj.id,
            'user_id': form_obj.user_id,
            'status': form_obj.status,
            'data': eval(str(form_obj.data, encoding='utf-8')),
            'last_upd_time': form_obj.last_upd_time.strftime('%Y-%m-%d %H:%M:%S'),
            'create_time': form_obj.create_time.strftime('%Y-%m-%d %H:%M:%S'),
        })

    #############################
    # 内部函数
    #############################
    @classmethod
    def _get_table_obj(cls, data_table):
        """
        获取指定表对象

        @param {str|class} data_table - 如果为str代表自定义的表名，如果为''代表使用默认表存储，否则为BaseModel对象

        @returns {class} - 返回实际表对象
        """
        FORM_PLUGIN_SELF_TABLE = RunTool.get_global_var('FORM_PLUGIN_SELF_TABLE')

        if type(data_table) == str:
            if data_table == '':
                # 通用存储
                return FormPluginData

            # 需动态生成表对象
            if data_table in FORM_PLUGIN_SELF_TABLE.keys():
                return FORM_PLUGIN_SELF_TABLE[data_table]
            else:
                FORM_PLUGIN_SELF_TABLE[data_table] = type(
                    data_table, (FormPluginData,), {}
                )
                return FORM_PLUGIN_SELF_TABLE[data_table]
        else:
            # 为表对象，原样返回
            return data_table


#############################
# 数据初始化处理工具
#############################
DATA_TABLES = [FormPluginData]  # 数据表


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
        if logger is not None:
            logger.debug('remove leave message plugin data success!')

    @classmethod
    def remove_config(cls, qa_manager: QAManager, logger: Logger):
        """
        清空所有配置

        @param {QAManager} qa_manager - 数据管理对象
        @param {Logger} logger - 日志对象
        """
        # 标准问题和答案
        _std_q = StdQuestion.get_or_none(StdQuestion.tag == 'form_direct_action')
        if _std_q is not None:
            # 删除对应问题的意图
            _ret = NlpPurposConfigDict.delete().where(
                NlpPurposConfigDict.std_question_id == _std_q.id
            ).execute()
            if logger is not None:
                logger.debug(
                    'remove form plugin nlp config success: %s !' % str(_ret))

            _ret = Answer.delete().where(
                Answer.std_question_id == _std_q.id
            ).execute()
            _ret = StdQuestion.delete().where(StdQuestion.id == _std_q.id).execute()
            if logger is not None:
                logger.debug(
                    'remove form plugin std question config success: %s !' % str(_ret))

    @classmethod
    def import_config(cls, qa_manager: QAManager, logger: Logger):
        """
        添加标准配置(不考虑删除问题)

        @param {QAManager} qa_manager - 数据管理对象
        @param {Logger} logger - 日志对象
        """
        FORM_PLUGIN_CONFIG = RunTool.get_global_var('FORM_PLUGIN_CONFIG')
        if FORM_PLUGIN_CONFIG is None:
            FORM_PLUGIN_CONFIG = dict()
            RunTool.set_global_var('FORM_PLUGIN_CONFIG', FORM_PLUGIN_CONFIG)

        FORM_PLUGIN_SELF_TABLE = RunTool.get_global_var('FORM_PLUGIN_SELF_TABLE')
        if FORM_PLUGIN_SELF_TABLE is None:
            FORM_PLUGIN_SELF_TABLE = dict()
            RunTool.set_global_var('FORM_PLUGIN_SELF_TABLE', FORM_PLUGIN_SELF_TABLE)

        # 插入标准问题
        _std_q = StdQuestion.create(
            tag='form_direct_action',
            q_type='context', milvus_id=-1, collection=FORM_PLUGIN_COLLECTION,
            partition=FORM_PLUGIN_PARTITION,
            question='表单插件通用处理'
        )

        # 插入问题答案
        Answer.create(
            std_question_id=_std_q.id, a_type='job',
            type_param="['FormPlugin', 'operate', {}]",
            replace_pre_def='N',
            answer='表单插件通用处理'
        )

        if logger is not None:
            logger.info('create form plugin std question config success!')

        # 处理扩展插件
        if FORM_PLUGIN_SEARCH_PATH is not None:
            _path = os.path.join(os.path.dirname(__file__), FORM_PLUGIN_SEARCH_PATH)
            _file_list = FileTool.get_filelist(path=_path, regex_str=r'.*\.py$', is_fullname=False)
            for _file in _file_list:
                if _file == '__init__.py':
                    continue

                # 执行加载
                _module = ImportTool.import_module(_file[0: -3], extend_path=_path, is_force=True)
                _clsmembers = inspect.getmembers(_module, inspect.isclass)
                for (_class_name, _class) in _clsmembers:
                    if _module.__name__ != _class.__module__:
                        # 不是当前模块定义的函数
                        continue

                    # 判断类型
                    _get_form_type = getattr(_class, 'get_form_type', None)
                    if _get_form_type is None or not callable(_get_form_type):
                        # 不是标准的插件类
                        continue

                    _form_type = _get_form_type()
                    _get_form_config = getattr(_class, 'get_form_config', None)

                    # 加入配置
                    FORM_PLUGIN_CONFIG[_form_type] = _get_form_config()

        # 循环插件实例进行处理
        for _form_type in FORM_PLUGIN_CONFIG.keys():
            _config = FORM_PLUGIN_CONFIG[_form_type]

            # 创建表单类型意图参数
            NlpPurposConfigDict.create(
                action=_form_type,
                match_collection='', match_partition='',
                collection=FORM_PLUGIN_COLLECTION,
                partition=FORM_PLUGIN_PARTITION,
                std_question_id=_std_q.id,
                order_num=_config['order_num'],
                exact_match_words=str(_config['exact_match_words']),
                exact_ignorecase=_config['exact_ignorecase'],
                match_words=str(_config['match_words']),
                ignorecase=_config['ignorecase'], word_scale=_config['word_scale'],
                info=str(_config['info']),
                check=str(_config['check'])
            )

            if logger is not None:
                logger.info('create form plugin [%s] success!' % _form_type)


#############################
# 插件
#############################
class FormPlugin(object):
    """
    表单插件Job插件
    """
    @classmethod
    def plugin_type(cls):
        """
        必须定义的函数，返回插件类型
        """
        return 'job'

    @classmethod
    def initialize(cls, loader, qa_manager, qa, **kwargs):
        """
        装载插件前执行的初始化处理
        可以不定义

        @param {QAServerLoader} loader - 服务装载器
        @param {QAManager} qa_manager - 数据管理
        @param {QA} qa - 问答服务
        """
        FORM_PLUGIN_CONFIG = RunTool.get_global_var('FORM_PLUGIN_CONFIG')
        if FORM_PLUGIN_CONFIG is None:
            FORM_PLUGIN_CONFIG = dict()
            RunTool.set_global_var('FORM_PLUGIN_CONFIG', FORM_PLUGIN_CONFIG)

        FORM_PLUGIN_SELF_TABLE = RunTool.get_global_var('FORM_PLUGIN_SELF_TABLE')
        if FORM_PLUGIN_SELF_TABLE is None:
            FORM_PLUGIN_SELF_TABLE = dict()
            RunTool.set_global_var('FORM_PLUGIN_SELF_TABLE', FORM_PLUGIN_SELF_TABLE)

        # 获取表单实例库
        if FORM_PLUGIN_SEARCH_PATH is not None:
            _path = os.path.join(os.path.dirname(__file__), FORM_PLUGIN_SEARCH_PATH)
            _file_list = FileTool.get_filelist(path=_path, regex_str=r'.*\.py$', is_fullname=False)
            for _file in _file_list:
                if _file == '__init__.py':
                    continue

                # 执行加载
                _module = ImportTool.import_module(_file[0: -3], extend_path=_path, is_force=True)
                _clsmembers = inspect.getmembers(_module, inspect.isclass)
                for (_class_name, _class) in _clsmembers:
                    if _module.__name__ != _class.__module__:
                        # 不是当前模块定义的函数
                        continue

                    # 判断类型
                    _get_form_type = getattr(_class, 'get_form_type', None)
                    if _get_form_type is None or not callable(_get_form_type):
                        # 不是标准的插件类
                        continue

                    _form_type = _get_form_type()
                    _get_form_config = getattr(_class, 'get_form_config', None)

                    # 加入配置
                    FORM_PLUGIN_CONFIG[_form_type] = _get_form_config()

        # 循环插件实例进行处理
        for _form_type in FORM_PLUGIN_CONFIG.keys():
            _config = FORM_PLUGIN_CONFIG[_form_type]

            # 执行初始化
            _initialize_fun = _config.get('initialize_fun', None)
            if _initialize_fun is not None:
                _initialize_fun(loader, qa_manager, qa, **kwargs)

    @classmethod
    def operate(cls, question: str, session_id: str, match_list: list,
                qa: QA, qa_manager: QAManager, **kwargs) -> list:
        """
        表单处理

        @param {str} question - 原始问题
        @param {str} session_id - session_id
        @param {list} match_list - 匹配上的问题、答案对象: [(StdQuestion, Answer)]
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 扩展传入参数
            ids {list} - 随机标准问题id清单

        @returns {list} - 按照不同的处理要求返回内容
            'answer', [str, ...]  - 直接返回回复内容，第二个参数为回复内容
                注：如果第二个参数返回None代表使用传入的答案的answer字段作为提示
            'to', int - 跳转到指定问题处理，第二个参数为std_question_id
        """
        FORM_PLUGIN_CONFIG = RunTool.get_global_var('FORM_PLUGIN_CONFIG')

        if 'action' in kwargs.keys():
            # 通过操作意图发起，为创建表单操作
            _form_type = kwargs['action']
            _op_para = {'action': 'create'}
        else:
            # 非表单发起操作，问题为一个json对象
            _op_para = eval(question)
            _form_type = _op_para['form_type']

        # 检查表单类型
        if _form_type not in FORM_PLUGIN_CONFIG.keys():
            # 不存在对应的表单类型
            return 'answer', [FORM_PLUGIN_TIPS['unsupport_form_type'], ]

        _form_config = FORM_PLUGIN_CONFIG[_form_type]

        # 执行操作预处理
        _op_predeal_fun = _form_config.get('op_predeal_fun', None)
        if _op_predeal_fun is None:
            _op_predeal_fun = cls._op_predeal_fun
        _action, _action_para = _op_predeal_fun(
            _op_para, question, session_id, qa, qa_manager, **kwargs
        )

        # 判断操作并执行后续的处理
        if _action in ['answer', 'to']:
            return _action, _action_para
        elif _action == 'create':
            # 创建表单
            if _form_config['default_fun'] is None:
                _default = dict()
            else:
                _default = _form_config['default_fun'](
                    question, session_id, qa, qa_manager, **kwargs
                )

            # 组织返回的表单创建信息
            _form_info = {
                'data_type': 'form',
                'form_type': _form_type,
                'action': 'create',
                'name': _form_config['name'],
                'std_question_id': match_list[0][0].id,
                'default': _default,
            }

            # 增加表单字段定义
            if _form_config['answer_with_def']:
                _form_info['preview_def'] = _form_config['preview_def']
                _form_info['form_def'] = _form_config['form_def']

            # 以字典形式返回结果
            return 'answer', [_form_info, ]
        elif _action == 'save':
            # 保存表单
            _form_obj = FormPluginApi.save_form(_op_para, session_id, qa, qa_manager)

            _saved_tips = _form_config.get('saved_tips', None)
            if _saved_tips is not None:
                # 返回提示
                return 'answer', [_saved_tips, ]
            else:
                # 返回预览信息
                _form_info = FormPluginApi.get_form_preview_dict(
                    _form_obj, std_question_id=match_list[0][0].id
                )
                return 'answer', [_form_info, ]
        elif _action == 'upd':
            # 更新表单
            _form_obj = FormPluginApi.upd_form(_op_para, session_id, qa, qa_manager)
            if _form_obj is None:
                # 表单不存在
                return 'answer', [FORM_PLUGIN_TIPS['form_not_exists'], ]

            _upd_tips = _form_config.get('upd_tips', None)
            if _upd_tips is not None:
                # 返回提示
                return 'answer', [_upd_tips, ]
            else:
                # 返回预览信息
                _form_info = FormPluginApi.get_form_preview_dict(
                    _form_obj, std_question_id=match_list[0][0].id
                )
                return 'answer', [_form_info, ]
        elif _action == 'preview':
            # 获取表单预览信息
            _form_obj = FormPluginApi.get_form_obj(_op_para, session_id, qa, qa_manager)
            if _form_obj is None:
                # 表单不存在
                return 'answer', [FORM_PLUGIN_TIPS['form_not_exists'], ]

            # 返回预览信息
            _form_info = FormPluginApi.get_form_preview_dict(
                _form_obj, std_question_id=match_list[0][0].id
            )
            return 'answer', [_form_info, ]
        elif _action == 'get':
            # 获取表单完整信息
            _form_obj = FormPluginApi.get_form_obj(_op_para, session_id, qa, qa_manager)
            if _form_obj is None:
                # 表单不存在
                return 'answer', [FORM_PLUGIN_TIPS['form_not_exists'], ]

            # 返回详细信息
            _form_info = FormPluginApi.get_form_info_dict(
                _form_obj, std_question_id=match_list[0][0].id)
            return 'answer', [_form_info, ]
        else:
            # 不支持的表单类型
            return 'answer', [FORM_PLUGIN_TIPS['unsupport_form_action']]

    #############################
    # 内部函数
    #############################
    @classmethod
    def _op_predeal_fun(cls, op_para: dict, question: str, session_id: str,
                        qa: QA, qa_manager: QAManager, **kwargs):
        """
        默认的表单操作预处理函数

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
        # 默认不改变操作模式
        return op_para['action'], None


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))

    # 命令方式：python form.py op=reset type=all
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
