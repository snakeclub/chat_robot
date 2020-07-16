#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
知识库问答插件
@module knowledge
@file knowledge.py
"""
import os
import sys
import datetime
import re
import shutil
import traceback
import peewee as pw
import pandas as pd
import numpy as np
from HiveNetLib.base_tools.file_tool import FileTool
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.qa import QA
from chat_robot.lib.data_manager import QAManager
from chat_robot.lib.answer_db import BaseModel, AnswerDao, NlpPurposConfigDict


__MOUDLE__ = 'knowledge'  # 模块名
__DESCRIPT__ = u'知识库问答插件'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.07.12'  # 发布日期


#############################
# 数据库模型
#############################
class KnowledgImages(BaseModel):
    """
    知识库图片库
    """
    id = pw.BigAutoField()  # 图片id
    url = pw.CharField()  # 图片的访问url地址
    notes = pw.CharField(default='')  # 图片的说明

    class Meta:
        # 定义数据库表名
        table_name = 'knowledge_images'


class KnowledgeBooks(BaseModel):
    """
    知识库书本/文章
    """
    id = pw.BigAutoField()  # 书本ID
    name = pw.CharField(index=True)  # 书名
    summary = pw.CharField(max_length=1000, default='')  # 摘要
    author = pw.CharField(default='')  # 作者
    create_time = pw.DateTimeField(default=datetime.datetime.now)  # 创建时间

    class Meta:
        # 定义数据库表名
        table_name = 'knowledge_books'


class KnowledgeChapters(BaseModel):
    """
    知识库章节
    """
    id = pw.BigAutoField(primary_key=True)  # 章节ID
    c_type = pw.CharField(
        choices=[('catalog', '目录'), ('content', '章节内容'), ('section', '分段内容')],
        default='content',
    )  # 章节类型，如果是catalog，代表只包含章节标题，无章节内容；如果是sub，代表是其父章节过长拆分出来的多个分段
    collection = pw.CharField()  # 知识对应问题所属分类集
    partition = pw.CharField(default='')  # 知识对应问题所属场景
    book_id = pw.BigIntegerField(index=True)  # 所属书本id
    parent_chapter_id = pw.BigIntegerField(default=0, index=True)  # 父章节id
    last_chapter_id = pw.BigIntegerField(default=0, index=True)  # 上一章节id
    c_class = pw.CharField()  # 知识章节分类
    title = pw.CharField()  # 章节标题
    content = pw.CharField(max_length=4000, default='')  # 章节内容，存储的文本格式需要与客户端约定，是富文本还是普通文本
    image_id = pw.BigIntegerField(default=0)  # 章节显示图片id
    image_para = pw.CharField(default='')  # 显示图片参数，需与客户端约定，例如left/right等位置信息
    create_time = pw.DateTimeField(default=datetime.datetime.now)  # 创建时间

    class Meta:
        # 定义数据库表名
        table_name = 'knowledge_chapters'


#############################
# 公共参数
#############################
KNOWLEDGE_DATA_IMPORT = True  # 是否导入数据，请在导入数据后修改为False
KNOWLEDGE_DATA_PATH = './knowledge'  # 知识库导入文件目录，以当前插件路径为相对路径
KNOWLEDGE_DATA_FILENAME = 'knowledge_data.xlsx'  # 知识库导入文件名

KNOWLEDGE_RESET_DB = True  # 是否重置数据库，请在导入数据后修改为Fasle
KNOWLEDGE_DELETE_COLLECTIONS = ['k_jadeite']  # 在重置数据库的情况下，要删除的collecton清单
KNOWLEDGE_DB_TABLES = [KnowledgeChapters, KnowledgeBooks, KnowledgImages]  # 表清单

UPLOAD_IMAGE_PATH = '../client/static/knowledge/images'  # 上传图片存储路径（需手工放入网站的静态路径中）
WEB_IMAGE_URL = '/static/knowledge/images/'  # 网站静态图片访问地址
TRUNCATE_IMAGE_PATH = True  # 是否清空目标图片存储路径

SECTION_NUM_SHOW_LIMIT = 2  # 子段落一次显示的数量


#############################
# 控制指令相关配置
#############################
RESET_ACTION_DICT = True  # 是否清除指令字典
ACTION_COLLECTION = 'knowledge'  # 固定的控制意图匹配问题分类
ACTION_PARTITION = 'control'  # 固定的控制意图匹配问题分类场景
# 指令字典，与NlpPurposConfigDict的配置一致，注意关键词要加到用户字典中
ACTION_DICT = {
    # 如果知识点只显示了一半，继续显示后面的内容
    'more': {
        'order_num': 0,  # 匹配顺序
        'exact_match_words': ['更多', 'm', 'more', '继续', '向后'],  # 精确指令
        'exact_ignorecase': 'Y',  # 忽略大小写
        'match_words': ['更多', 'more', '继续', '向后'],  # 分词模式匹配
        'ignorecase': 'Y',  # 是否忽略大小写
        'word_scale': 0.66,  # 分词模式必须超过2/3比例
        'info': [],  # 获取方法配置
        'check': [],  # 检查方法配置
    },
    # 下一个知识点
    'next': {
        'order_num': 0,  # 匹配顺序
        'exact_match_words': ['下一个', 'n', 'next', '后一个', '继续', '向后'],  # 精确指令
        'exact_ignorecase': 'Y',  # 忽略大小写
        'match_words': ['下一个', 'next', '继续', '后一个', '向后'],  # 分词模式匹配
        'ignorecase': 'Y',  # 是否忽略大小写
        'word_scale': 0.66,  # 分词模式必须超过2/3比例
        'info': [],  # 获取方法配置
        'check': [],  # 检查方法配置
    },
    # 上一个知识点
    'prev': {
        'order_num': 0,  # 匹配顺序
        'exact_match_words': ['上一个', 'p', 'prev', '前一个', '向前'],  # 精确指令
        'exact_ignorecase': 'Y',  # 忽略大小写
        'match_words': ['上一个', 'prev', '前一个', '向前'],  # 分词模式匹配
        'ignorecase': 'Y',  # 是否忽略大小写
        'word_scale': 0.66,  # 分词模式必须超过2/3比例
        'info': [],  # 获取方法配置
        'check': [],  # 检查方法配置
    },
    # 获取帮助
    'help': {
        'order_num': 0,  # 匹配顺序
        'exact_match_words': ['帮助', 'h', 'help'],  # 精确指令
        'exact_ignorecase': 'Y',  # 忽略大小写
        'match_words': ['帮助', 'help'],  # 分词模式匹配
        'ignorecase': 'Y',  # 是否忽略大小写
        'word_scale': 0.66,  # 分词模式必须超过2/3比例
        'info': [],  # 获取方法配置
        'check': [],  # 检查方法配置
    },
}

# 知识库处理遇到问题的提示
HELP_TIPS = [
    '知识查看帮助:',
    '1. 输入以下指令查看当前知识点的更多内容: "%s"' % '" 或 "'.join(ACTION_DICT['more']['exact_match_words'][0:2]),
    '2. 输入以下指令查看下一个知识点内容: "%s"' % '" 或 "'.join(ACTION_DICT['next']['exact_match_words'][0:2]),
    '3. 输入以下指令查看上一个知识点内容: "%s"' % '" 或 "'.join(ACTION_DICT['prev']['exact_match_words'][0:2]),
    '4. 输入以下指令查看帮助: "%s"' % '" 或 "'.join(ACTION_DICT['help']['exact_match_words'][0:2]),
]
ACTION_TIPS = {
    'no_more': '已无更多内容, 可回复"%s"或"%s"获取下一个知识，或者回复您想要查找的其他知识点内容' % (ACTION_DICT['next']['exact_match_words'][0], ACTION_DICT['next']['exact_match_words'][1]),
    'last_chapter': '已是最后一个知识点，可回复您想要查找的其他知识点内容',
    'first_chapter': '已是第一个知识点，可回复您想要查找的其他知识点内容',
    'help': '<br>'.join(HELP_TIPS),
    'more_tips': '如果要查看更多内容，请回复"%s"或"%s"' % (ACTION_DICT['more']['exact_match_words'][0], ACTION_DICT['more']['exact_match_words'][1])
}


#############################
# 知识库问答插件
#############################
class KnowledgeAsk(object):
    """
    知识库问答插件
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
        # 导入知识库
        cls._import_knowledge_data(loader)

    @classmethod
    def get_chapter(cls, question: str, session_id: str, context_id: str, std_question_id: int,
                    collection: str, partition: str,
                    qa: QA, qa_manager: QAManager, **kwargs):
        """
        获取章节信息

        @param {str} question - 客户反馈的信息文本(提问回答)
        @param {str} session_id - 客户的session id
        @param {str} context_id - 上下文临时id
        @param {int} std_question_id - 上下文中对应的提问问题id
        @param {str} collection - 提问答案参数指定的问题分类
        @param {str} partition - 提问答案参数指定的场景标签
        @param {QA} qa - 服务器的问答处理模块实例对象
        @param {QAManager} qa_manager - 服务器的问答数据管理实例对象
        @param {kwargs} - 扩展传入参数
            chapter_id {int} - 匹配到的章节id

        @param {str, object} - 按照不同的处理要求返回内容
            'answer', [str, ...]  - 直接返回回复内容，第二个参数为回复内容
            'to', int - 跳转到指定问题处理，第二个参数为std_question_id
            'again', [str, ...] - 再获取一次答案，第二个参数为提示内容，如果第2个参数为None代表使用原来的参数再提问一次
            'break', [collection, partition] - 跳出问题(让问题继续走匹配流程)，可以返回[collection, partition]变更分类和场景
            注意：
            1、默认为'again'
            2、第二个参数可以为dict字典，restful api返回的answer_type将为json

        """
        # 获取上下文信息
        _context_dict = qa.get_context_dict(session_id)
        if 'knowledge_control' not in _context_dict['ask'].keys():
            # 第一次进入问答模块，获取章节信息
            _chapter_dict = cls._get_chapter_content(kwargs['chapter_id'])

            # 生成控制字典并放入上下文
            _context_dict['ask']['knowledge_control'] = {
                'current_id': _chapter_dict['current_id'],
                'parent_id': _chapter_dict['parent_id'],
                'last_id': _chapter_dict['last_id'],
                'c_type': _chapter_dict['c_type'],
                'more': _chapter_dict['more'],
                'book_id': _chapter_dict['book_id'],
            }
            qa.add_ask_context(session_id, _context_dict['ask'])

            if _chapter_dict['more']:
                _chapter_dict['contents'].append(
                    {
                        'content': ACTION_TIPS['more_tips'],  # 章节内容
                        'images': None
                    }
                )

            # 返回知识章节内容
            return 'again', [{
                'data_type': 'knowledge_content',
                'title': _chapter_dict['title'],
                'contents': _chapter_dict['contents']
            }]
        else:
            # 第二次进入控制模块, 使用NLP语义解析尝试匹配意图
            _actions = qa.nlp.analyse_purpose(
                question, collection=ACTION_COLLECTION, partition=ACTION_PARTITION,
                is_multiple=False
            )
            if len(_actions) == 0:
                # 没有匹配到指令，删除上下文信息，重新匹配问题
                qa.clear_session_dict(session_id, 'context')
                return 'break', None

            # 执行指令处理
            _knowledge_control = _context_dict['ask']['knowledge_control']
            _ret_answers = None  # 要返回的内容二元组，如果要返回答案，请设设置值，例如：('again', ['test'])
            _chapter_dict = None  # 新获取到要回复的章节内容字典，如果有值代表要回复该内容
            if _actions[0]['action'] == 'next' or _actions[0]['action'] == 'more':
                if _actions[0]['action'] == 'more' and _knowledge_control['more']:
                    # 有更多章节内容的情况
                    _next_chapter: KnowledgeChapters = KnowledgeChapters.get_or_none(
                        KnowledgeChapters.last_chapter_id == _knowledge_control['current_id']
                    )
                    if _next_chapter is None:
                        _knowledge_control['more'] = False
                        _ret_answers = ('again', [ACTION_TIPS['no_more'], ])
                else:
                    # 都是找下一个章节
                    if _knowledge_control['c_type'] == 'section':
                        # 子段落的下一个章节需要找回父节点来处理
                        _parent_chapter: KnowledgeChapters = KnowledgeChapters.get_or_none(
                            KnowledgeChapters.id == _knowledge_control['parent_id']
                        )
                        _next_chapter: KnowledgeChapters = KnowledgeChapters.get_or_none(
                            (KnowledgeChapters.last_chapter_id == _parent_chapter.id) & (
                                KnowledgeChapters.c_type != 'section')
                        )
                    else:
                        _next_chapter: KnowledgeChapters = KnowledgeChapters.get_or_none(
                            KnowledgeChapters.last_chapter_id == _knowledge_control['current_id']
                        )

                    if _next_chapter is None:
                        # 已经是最后一个节点了
                        _ret_answers = ('again', [ACTION_TIPS['last_chapter'], ])

                # 获取下一节点信息字典
                if _next_chapter is not None:
                    _chapter_dict = cls._get_chapter_content(_next_chapter.id)
            elif _actions[0]['action'] == 'prev':
                # 上一个知识点
                _last_chapter_id = _knowledge_control['last_id']
                if _last_chapter_id == 0:
                    # 已经是第一个知识点
                    _ret_answers = ('again', [ACTION_TIPS['first_chapter'], ])
                else:
                    _chapter_dict = cls._get_chapter_content(_last_chapter_id)
            elif _actions[0]['action'] == 'help':
                # 帮助信息
                _ret_answers = ('again', [ACTION_TIPS['help'], ])

            # 处理最终的返回
            if _ret_answers is not None:
                return _ret_answers[0], _ret_answers[1]
            elif _chapter_dict is not None:
                # 生成控制字典并放入上下文
                _context_dict['ask']['knowledge_control'] = {
                    'current_id': _chapter_dict['current_id'],
                    'parent_id': _chapter_dict['parent_id'],
                    'last_id': _chapter_dict['last_id'],
                    'c_type': _chapter_dict['c_type'],
                    'more': _chapter_dict['more'],
                    'book_id': _chapter_dict['book_id'],
                }
                qa.add_ask_context(session_id, _context_dict['ask'])

                if _chapter_dict['more']:
                    _chapter_dict['contents'].append(
                        {
                            'content': ACTION_TIPS['more_tips'],  # 章节内容
                            'images': None
                        }
                    )

                # 返回知识章节内容
                return 'again', [{
                    'data_type': 'knowledge_content',
                    'title': _chapter_dict['title'],
                    'contents': _chapter_dict['contents']
                }]
            else:
                # 不支持的动作
                qa.clear_session_dict(session_id, 'context')
                return 'break', None

    #############################
    # 内部函数
    #############################
    @classmethod
    def _get_chapter_content(cls, chapter_id: int):
        """
        获取章节内容

        @param {int} chapter_id - 章节id

        @returns {dict} - 章节内容字典
            {
                'current_id': xx,  # 当前章节id
                'parent_id': xx,  # 当前章节的父id
                'last_id': xx,  # 当前章节的上一章节节点
                'c_type': xx,  # 当前章节类型
                'more': True/False,  # 是否有更多内容
                'book_id': xx,  # 书本id
                'title': xx,  # 当前章节显示标题
                'contents': [
                    {
                        'content': xx,  # 章节内容
                        'images': {
                            'id': xx,  # 图片id
                            'url': xx,  # 图片url地址
                            'notes': xx,  # 图片扩展信息
                            'para' : xx,  # 图片展示参数
                        },  # 图片信息，如果不涉及图片，该字典值为None
                    },
                    ...
                ]  # 显示内容，可以为多项
            }
        """
        _chapter: KnowledgeChapters = KnowledgeChapters.get(
            KnowledgeChapters.id == chapter_id)

        if _chapter.c_type == 'catalog':
            # 如果只是目录，要向下找到子孙节点的第一个content节点
            while _chapter.c_type == 'catalog':
                _chapter = KnowledgeChapters.get(
                    KnowledgeChapters.parent_chapter_id == _chapter.id
                )

        # 控制子段落获取的变量
        _start_id = _chapter.id  # 子段落的上一节点id
        if _chapter.c_type == 'section':
            _title = ''  # 章节标题，如果是子段落，无需再显示
            _parent_id = _chapter.parent_chapter_id  # 子段落的父节点id
            # 获取当前content的上一contentid
            _parent_chapter: KnowledgeChapters = KnowledgeChapters.get(
                KnowledgeChapters.id == _parent_id)
            _last_id = _parent_chapter.last_chapter_id
        else:
            _title = _chapter.title
            _parent_id = _chapter.id
            _last_id = _chapter.last_chapter_id

        # 将自身信息放入字典
        _chapter_dict = {
            'current_id': _chapter.id,  # 当前章节id
            'parent_id': _chapter.parent_chapter_id,  # 当前章节的父节点id
            'last_id': _last_id,  # 当前章节的上一章节节点
            'c_type': _chapter.c_type,  # 当前章节的类型
            'more': False,  # 是否有更多内容
            'book_id': _chapter.book_id,  # 书本id
            'title': _title,  # 当前章节显示标题
            'contents': [
                {
                    'content': _chapter.content,
                    'images': None if _chapter.image_id == 0 else cls._get_image_info(_chapter.image_id, _chapter.image_para)
                },
            ]  # 显示内容，可以为多项
        }

        # 查询子服务
        _query = KnowledgeChapters.select().where(
            (KnowledgeChapters.parent_chapter_id == _parent_id) & (
                KnowledgeChapters.last_chapter_id >= _start_id) & (
                KnowledgeChapters.last_chapter_id != KnowledgeChapters.id)
        )
        if _query.count() > SECTION_NUM_SHOW_LIMIT:
            # 剩余数量超过本次处理的数量
            _chapter_dict['more'] = True

        _sections = _query.order_by(
            KnowledgeChapters.last_chapter_id.asc()
        ).limit(SECTION_NUM_SHOW_LIMIT)

        for _row in _sections:
            _chapter_dict['current_id'] = _row.id
            _chapter_dict['parent_id'] = _row.parent_chapter_id
            _chapter_dict['c_type'] = _row.c_type
            _chapter_dict['contents'].append({
                'content': _row.content,
                'images': None if _row.image_id == 0 else cls._get_image_info(_row.image_id, _row.image_para)
            })

        # 返回结果
        return _chapter_dict

    @classmethod
    def _get_image_info(cls, image_id: int, image_para: str):
        """
        获取图片信息

        @param {int} image_id - 图片id
        @param {str} image_para - 图片显示参数

        @returns {dict} - 图片信息字典
            {
                id : int_图片id,
                url : str_图片url,
                notes : str_图片信息,
                para : str_图片展示参数
            }

        """
        _image = KnowledgImages.get(KnowledgImages.id == image_id)
        return {
            'id': image_id,
            'url': _image.url,
            'notes': _image.notes,
            'para': image_para
        }

    #############################
    # 数据导入相关
    #############################
    @classmethod
    def _import_knowledge_data(cls, loader):
        """
        导入知识库数据

        @param {QAServerLoader} loader - 服务装载器
        """
        if KNOWLEDGE_RESET_DB:
            # 根据参数删除表
            AnswerDao.drop_tables(KNOWLEDGE_DB_TABLES)
            if loader.logger is not None:
                loader.logger.debug('drop knowledge database tabels!')

            # 删除导入的参数
            for _collection in KNOWLEDGE_DELETE_COLLECTIONS:
                loader.qa_manager.delete_collection(_collection, with_question=True)

        if RESET_ACTION_DICT:
            # 重置操作意图字典
            _ret = NlpPurposConfigDict.delete().where(
                (NlpPurposConfigDict.match_collection == ACTION_COLLECTION) & (
                    NlpPurposConfigDict.match_partition == ACTION_PARTITION)
            ).execute()
            if loader.logger is not None:
                loader.logger.debug(
                    'delete nlp_purpos_config_dict knowledge config success: %s!' % str(_ret))

            # 导入匹配字典配置
            for _action in ACTION_DICT.keys():
                NlpPurposConfigDict.create(
                    action=_action,
                    match_collection=ACTION_COLLECTION, match_partition=ACTION_PARTITION,
                    std_question_id=0, order_num=ACTION_DICT[_action]['order_num'],
                    exact_match_words=str(ACTION_DICT[_action]['exact_match_words']),
                    exact_ignorecase=ACTION_DICT[_action]['exact_ignorecase'],
                    match_words=str(ACTION_DICT[_action]['match_words']),
                    ignorecase=ACTION_DICT[_action]['ignorecase'],
                    word_scale=ACTION_DICT[_action]['word_scale'],
                    info=str(ACTION_DICT[_action]['info']),
                    check=str(ACTION_DICT[_action]['check'])
                )
            if loader.logger is not None:
                loader.logger.debug(
                    'create nlp_purpos_config_dict knowledge config success: %s!' % str(ACTION_DICT))

            # 重新加载字典
            loader.qa_manager.load_nlp_purpos_config_dict()

        if TRUNCATE_IMAGE_PATH:
            # 删除上传文件目录
            FileTool.remove_all_with_path(
                os.path.join(os.path.dirname(__file__), UPLOAD_IMAGE_PATH)
            )
            if loader.logger is not None:
                loader.logger.debug('truncate knowledge upload image path!')

        # 创建表
        AnswerDao.create_tables(KNOWLEDGE_DB_TABLES)

        if not KNOWLEDGE_DATA_IMPORT:
            # 无需导入数据
            return

        # 开始导入数据
        _data_file = os.path.join(
            os.path.dirname(__file__), KNOWLEDGE_DATA_PATH, KNOWLEDGE_DATA_FILENAME
        )
        if not os.path.exists(_data_file):
            # 文件不存在
            return

        with pd.io.excel.ExcelFile(_data_file) as _excel_io:
            # 处理KnowledgImages
            _images_id_mapping = cls._import_knowledge_images(_excel_io, loader)

            # 处理KnowledgeBooks
            _books_id_mapping = cls._import_knowledge_books(_excel_io, loader)

            # 处理KnowledgeChapters
            cls._import_knowledge_chapters(_excel_io, loader, _images_id_mapping, _books_id_mapping)

    @classmethod
    def _import_knowledge_images(cls, excel_io, loader):
        """
        装载图片

        @param {object} excel_io - pd.io.excel.ExcelFile的IO文件
        @param {QAServerLoader} loader - 服务装载器

        @returns {dict} - 导入的图片id映射
        """
        _images_id_mapping = dict()  # 图片excel上的id和真实id的映射关系
        try:
            # 读取标题行
            _df_header = pd.read_excel(
                excel_io, sheet_name='KnowledgImages', nrows=0, engine=loader.qa_manager.excel_engine
            )
        except:
            _df_header = None  # 没有获取到指定的页

        if _df_header is not None:
            _skiprows = 1  # 跳过的记录数
            _columns = {i: col for i, col in enumerate(_df_header.columns.tolist())}
            _data_path = os.path.join(
                os.path.dirname(__file__), KNOWLEDGE_DATA_PATH
            )
            _upload_image_path = os.path.join(
                os.path.dirname(__file__), UPLOAD_IMAGE_PATH
            )
            FileTool.create_dir(_upload_image_path, exist_ok=True)  # 先创建目录
            _web_image_url = WEB_IMAGE_URL
            while True:
                # 循环处理
                _df = pd.read_excel(
                    excel_io, sheet_name='KnowledgImages', nrows=loader.qa_manager.excel_batch_num,
                    header=None, skiprows=_skiprows, engine=loader.qa_manager.excel_engine
                )
                _skiprows += loader.qa_manager.excel_batch_num

                if not _df.shape[0]:
                    # 获取不到数据
                    break

                # 变更标题
                _df.rename(columns=_columns, inplace=True)

                for _index, _row in _df.iterrows():
                    # 逐行添加标准问题, _index为行，_row为数据集
                    try:
                        # 处理真实图片地址
                        _url = _row['url']
                        _path = ''
                        if _url.startswith('{$image='):
                            _path = os.path.join(_data_path, 'images', _url[8: -2])
                        elif _url.startswith('{$file='):
                            _path = os.path.join(_data_path, _url[7: -2])

                        if _path != '':
                            # 复制图片到静态文件目录
                            _ext = FileTool.get_file_ext(_path)
                            _new_file_name = datetime.datetime.now().strftime('%Y%m%d%H%M%S.%f') + '.' + _ext
                            shutil.copyfile(_path, os.path.join(_upload_image_path, _new_file_name))
                            _url = _web_image_url + _new_file_name

                        # 插入图片信息
                        _k_image = KnowledgImages.create(
                            url=_url,
                            notes='' if str(_row['notes']) == 'nan' else _row['notes'],
                        )

                        # 插入映射关系
                        if str(_row['id']) != 'nan':
                            _images_id_mapping[_row['id']] = _k_image.id
                    except:
                        if loader.logger is not None:
                            loader.logger.error('imported knowledge_images [id: %s] [%s] error: %s' % (
                                str(_row['id']), _row['url'], traceback.format_exc()
                            ))

                if loader.logger is not None:
                    loader.logger.debug('imported knowledge_images[%d]: %s' % (_skiprows, str(_df)))

        # 返回映射
        return _images_id_mapping

    @classmethod
    def _import_knowledge_books(cls, excel_io, loader):
        """
        装载知识库书本/文章

        @param {object} excel_io - pd.io.excel.ExcelFile的IO文件
        @param {QAServerLoader} loader - 服务装载器

        @returns {dict} - 导入的书本id映射
        """
        _books_id_mapping = dict()  # 图片excel上的id和真实id的映射关系
        try:
            # 读取标题行
            _df_header = pd.read_excel(
                excel_io, sheet_name='KnowledgeBooks', nrows=0, engine=loader.qa_manager.excel_engine
            )
        except:
            _df_header = None  # 没有获取到指定的页

        if _df_header is not None:
            _skiprows = 1  # 跳过的记录数
            _columns = {i: col for i, col in enumerate(_df_header.columns.tolist())}
            while True:
                # 循环处理
                _df = pd.read_excel(
                    excel_io, sheet_name='KnowledgeBooks', nrows=loader.qa_manager.excel_batch_num,
                    header=None, skiprows=_skiprows, engine=loader.qa_manager.excel_engine
                )
                _skiprows += loader.qa_manager.excel_batch_num

                if not _df.shape[0]:
                    # 获取不到数据
                    break

                # 变更标题
                _df.rename(columns=_columns, inplace=True)

                for _index, _row in _df.iterrows():
                    # 逐行添加标准问题, _index为行，_row为数据集
                    try:
                        # 插入书本/文章信息
                        _k_book = KnowledgeBooks.create(
                            name=_row['name'],
                            summary='' if str(_row['summary']) == 'nan' else _row['summary'],
                            author='' if str(_row['author']) == 'nan' else _row['author']
                        )

                        # 插入映射关系
                        if str(_row['id']) != 'nan':
                            _books_id_mapping[_row['id']] = _k_book.id
                    except:
                        if loader.logger is not None:
                            loader.logger.error('imported knowledge_books [id: %s] [%s] error: %s' % (
                                str(_row['id']), _row['name'], traceback.format_exc()
                            ))

                if loader.logger is not None:
                    loader.logger.debug('imported knowledge_books[%d]: %s' % (_skiprows, str(_df)))

        # 返回映射
        return _books_id_mapping

    @classmethod
    def _import_knowledge_chapters(cls, excel_io, loader, images_id_mapping: dict, books_id_mapping: dict):
        """
        导入章节

        @param {object} excel_io - pd.io.excel.ExcelFile的IO文件
        @param {QAServerLoader} loader - 服务装载器
        @param {dict} images_id_mapping - 图像的id映射字典
        @param {dict} books_id_mapping - 书本的id映射字典
        """
        _chapters_id_mapping = dict()  # 图片excel上的id和真实id的映射关系
        # 章节清单, key为章节id，value为[章节类型, 父节点id, 上一节点id, 子孙节点中最后一个content节点id]，注意这个id都是实际数据库id
        _chapters_tree = dict()
        _catalogs = list()  # 按顺序登记所有的目录id
        _cache_chapter_id = 0  # 上一节点id
        _qa_manager: QAManager = loader.qa_manager
        try:
            # 读取标题行
            _df_header = pd.read_excel(
                excel_io, sheet_name='KnowledgeChapters', nrows=0, engine=loader.qa_manager.excel_engine
            )
        except:
            _df_header = None  # 没有获取到指定的页

        if _df_header is not None:
            _skiprows = 1  # 跳过的记录数
            _columns = {i: col for i, col in enumerate(_df_header.columns.tolist())}
            while True:
                # 循环处理
                _df = pd.read_excel(
                    excel_io, sheet_name='KnowledgeChapters', nrows=loader.qa_manager.excel_batch_num,
                    header=None, skiprows=_skiprows, engine=loader.qa_manager.excel_engine
                )
                _skiprows += loader.qa_manager.excel_batch_num

                if not _df.shape[0]:
                    # 获取不到数据
                    break

                # 变更标题
                _df.rename(columns=_columns, inplace=True)

                for _index, _row in _df.iterrows():
                    # 逐行添加标准问题, _index为行，_row为数据集
                    try:
                        # 处理父节点和上一节点的关系，先获取excel中的值
                        if str(_row['parent_chapter_id']) == 'nan':
                            _parent_chapter_id = -1
                        else:
                            _parent_chapter_id = _chapters_id_mapping.get(
                                _row['parent_chapter_id'], _row['parent_chapter_id'])

                        if str(_row['last_chapter_id']) == 'nan':
                            _last_chapter_id = -1
                        else:
                            _last_chapter_id = _chapters_id_mapping.get(
                                _row['last_chapter_id'], _row['last_chapter_id'])

                        # 对于空的情况进行取值处理
                        if _parent_chapter_id == -1 or _last_chapter_id == -1:
                            if _cache_chapter_id == 0:
                                # 是第一个
                                if _parent_chapter_id == -1:
                                    _parent_chapter_id = 0
                                if _last_chapter_id == -1:
                                    _last_chapter_id = 0
                            elif _row['c_type'] == 'section':
                                if _chapters_tree[_cache_chapter_id][0] == 'section':
                                    # 上一节点也是段落
                                    if _parent_chapter_id == -1:
                                        # 段落的父节点跟上一个段落的一致
                                        _parent_chapter_id = _chapters_tree[_cache_chapter_id][1]
                                    if _last_chapter_id == -1:
                                        # 上一节点紧跟就好
                                        _last_chapter_id = _cache_chapter_id
                                else:
                                    # 上一节点是content
                                    if _parent_chapter_id == -1:
                                        _parent_chapter_id = _cache_chapter_id
                                    if _last_chapter_id == -1:
                                        # 父节点也是自己的上一节点
                                        _last_chapter_id = _cache_chapter_id
                            elif _row['c_type'] == 'content':
                                if _chapters_tree[_cache_chapter_id][0] == 'content':
                                    # 上一节点也是文章
                                    if _parent_chapter_id == -1:
                                        _parent_chapter_id = _chapters_tree[_cache_chapter_id][1]
                                    if _last_chapter_id == -1:
                                        _last_chapter_id = _cache_chapter_id
                                elif _chapters_tree[_cache_chapter_id][0] == 'section':
                                    # 上一节点是段落, 获取段落父节点content
                                    _section_parent_id = _chapters_tree[_cache_chapter_id][1]
                                    if _parent_chapter_id == -1:
                                        _parent_chapter_id = _chapters_tree[_section_parent_id][1]
                                    if _last_chapter_id == -1:
                                        _last_chapter_id = _section_parent_id
                                else:
                                    # 上一节点是目录catalog
                                    if _parent_chapter_id == -1:
                                        _parent_chapter_id = _cache_chapter_id
                                    if _last_chapter_id == -1:
                                        # 找到上一个目录catalog的最后一个子节点
                                        _last_catalog = _chapters_tree[_cache_chapter_id][2]
                                        if _last_catalog > 0:
                                            _last_chapter_id = _chapters_tree[_last_catalog][3]
                                        else:
                                            _last_chapter_id = 0
                            else:
                                #  当前节点是目录的情况，获取上一个catalog节点
                                _len_catalogs = len(_catalogs)
                                _last_catalog_id = 0
                                if _len_catalogs > 0:
                                    _last_catalog_id = _catalogs[_len_catalogs - 1]
                                if _last_catalog_id == 0:
                                    if _parent_chapter_id == -1:
                                        _parent_chapter_id = 0
                                    if _last_chapter_id == -1:
                                        _last_chapter_id = 0
                                else:
                                    if _parent_chapter_id == -1:
                                        _parent_chapter_id = _chapters_tree[_last_catalog_id][1]
                                    if _last_chapter_id == -1:
                                        _last_chapter_id = _last_catalog_id

                        # 插入章节信息
                        _k_chapter = KnowledgeChapters.create(
                            c_type=_row['c_type'],
                            collection=_row['collection'],
                            partition='' if str(_row['partition']) == 'nan' else _row['partition'],
                            book_id=books_id_mapping.get(_row['book_id'], _row['book_id']),
                            parent_chapter_id=_parent_chapter_id,
                            last_chapter_id=_last_chapter_id,
                            c_class=_row['c_class'],
                            title=_row['title'],
                            content='' if str(_row['content']) == 'nan' else _row['content'],
                            image_id=0 if str(_row['image_id']) == 'nan' else images_id_mapping.get(
                                _row['image_id'], _row['image_id']),
                            image_para='' if str(
                                _row['image_para']) == 'nan' else _row['image_para'],
                        )

                        # 处理树结构, [章节类型, 父节点id, 上一节点id, 子孙节点中最后一个content节点id]
                        _chapters_tree[_k_chapter.id] = [
                            _row['c_type'], _parent_chapter_id, _last_chapter_id, _k_chapter.id
                        ]
                        # 更新所有父节点的最后一个content节点id
                        if _row['c_type'] == 'content':
                            _temp_id = _parent_chapter_id
                            while _temp_id > 0:
                                _chapters_tree[_temp_id][3] = _k_chapter.id
                                _temp_id = _chapters_tree[_temp_id][1]
                        # 如果是目录
                        if _row['c_type'] == 'catalog':
                            _catalogs.append(_k_chapter.id)

                        _cache_chapter_id = _k_chapter.id

                        # 插入映射关系
                        if str(_row['id']) != 'nan':
                            _chapters_id_mapping[_row['id']] = _k_chapter.id

                        # 插入标准问题和扩展问题
                        if str(_row['match_std_question']) != 'nan' and _row['match_std_question'] != '':
                            _std_q_id = _qa_manager.add_std_question(
                                _row['match_std_question'],
                                collection=_k_chapter.collection,
                                q_type='ask', partition=_k_chapter.partition,
                                answer='知识库章节匹配问题答案', a_type='ask',
                                replace_pre_def='N',
                                a_type_param="['KnowledgeAsk', 'get_chapter', '%s', '%s', {'chapter_id': %s}, 'true']" % (
                                    _k_chapter.collection, _k_chapter.partition, str(_k_chapter.id)
                                )
                            )

                            # 插入扩展问题
                            if str(_row['extend_questions']) != 'nan':
                                _questions = _row['extend_questions'].replace('\r', '').split('\n')
                                for _question in _questions:
                                    if _question.strip() != '':
                                        _qa_manager.add_ext_question(_std_q_id, _question.strip())

                    except:
                        if loader.logger is not None:
                            loader.logger.error('imported knowledge_chapters [id: %s] [%s] error: %s' % (
                                str(_row['id']), _row['title'], traceback.format_exc()
                            ))

                if loader.logger is not None:
                    loader.logger.debug(
                        'imported knowledge_chapters[%d]: %s' % (_skiprows, str(_df))
                    )


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))
