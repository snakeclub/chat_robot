#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
问答数据管理
@module data_manager
@file data_manager.py
"""

import os
import sys
import copy
import math
import time
import json
import re
from functools import reduce
import numpy as np
import milvus as mv
import pandas as pd
from bert_serving.client import BertClient
from HiveNetLib.base_tools.run_tool import RunTool
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from chat_robot.lib.answer_db import AnswerDao, CollectionOrder, StdQuestion, Answer, ExtQuestion, NoMatchAnswers, CommonPara, NlpSureJudgeDict, NlpPurposConfigDict


__MOUDLE__ = 'data_manager'  # 模块名
__DESCRIPT__ = u'问答数据管理'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.06.24'  # 发布日期


# 答案库表清单
ANSWERDB_TABLES = [
    Answer, StdQuestion, ExtQuestion, CollectionOrder, NoMatchAnswers,
    CommonPara, NlpSureJudgeDict, NlpPurposConfigDict
]


class QAManager(object):
    """
    问答数据管理
    """

    def __init__(self, answer_db_para: dict, milvus_para: dict, bert_para: dict,
                 logger=None, excel_batch_num=100, excel_engine='xlrd'):
        """
        问答数据管理

        @param {dict} answer_db_para - 数据库连接参数，server.xml的answerdb配置
        @param {dict} milvus_para - Milvus服务连接参数，server.xml的milvus配置
        @param {dict} bert_para - BERT服务连接参数，server.xml的bert_client配置
        @param {bool} logger=None - 日志对象
        @param {int} excel_batch_num=100 - excel导入数据时每批处理的数据记录数
        @param {string} excel_engine='xlrd' - excel导入数据使用的引擎，可以是xlrd或者openpyxl
        """
        # 基础参数
        self.logger = logger
        self.excel_batch_num = excel_batch_num  # 处理excel时一次处理的数据量
        self.excel_engine = excel_engine  # 使用读引擎，可以是xlrd或者openpyxl

        # 装载数据库连接
        self.answer_db_para = copy.deepcopy(answer_db_para)
        self.database = AnswerDao.init_answerdb(self.answer_db_para)

        # 创建业务表
        AnswerDao.create_tables(ANSWERDB_TABLES)

        # milvus连接参数
        self.milvus_para = copy.deepcopy(milvus_para)
        self.index_file_size = self.milvus_para.get('index_file_size', 1024)
        self.dimension = self.milvus_para.get('dimension', 768)
        self.metric_type = eval('mv.MetricType.%s' % self.milvus_para.get('metric_type', 'IP'))
        self.nlist = self.milvus_para.get('nlist', 16384)

        # bert连接参数
        self.bert_para = copy.deepcopy(bert_para)

        # 获取CollectionOrder到内存
        self.sorted_collection = self._get_sorted_collection_list()

        # 获取缓存参数到内存
        self.DATA_MANAGER_PARA = dict()
        self.DATA_MANAGER_PARA['common_para'] = dict()
        self.load_common_para()
        self.load_nlp_sure_judge_dict()
        self.load_nlp_purpos_config_dict()

    #############################
    # 工具函数
    #############################

    def confirm_milvus_status(self, status: mv.Status, fun_name: str):
        """
        确认milvus执行结果，如果失败抛出异常

        @param {mv.Status} status - 执行结果
        @param {str} fun_name - 执行函数名
        """
        if status.code != 0:
            raise RuntimeError('execute milvus.%s error: %s' % (fun_name, str(status)))

    def get_milvus(self) -> mv.Milvus:
        """
        获取可用的milvus连接对象

        @returns {Milvus} - 返回要使用的Milvus对象
        """
        return mv.Milvus(
            host=self.milvus_para['host'], port=self.milvus_para['port'],
            pool=self.milvus_para.get('pool', 'SingletonThread')
        )

    def get_bert_client(self) -> BertClient:
        """
        获取可用的bert客户端

        @returns {BertClient} - 返回要使用的bert客户端
        """
        return BertClient(**self.bert_para)

    def normaliz_vec(self, vec_list):
        """
        标准化向量列表

        @param {list} vec_list - 通过bert产生的变量列表

        @returns {list} - 标准化后的向量列表
        """
        for i in range(len(vec_list)):
            vec = vec_list[i]
            square_sum = reduce(lambda x, y: x + y, map(lambda x: x * x, vec))
            sqrt_square_sum = np.sqrt(square_sum)
            coef = 1 / sqrt_square_sum
            vec = list(map(lambda x: x * coef, vec))
            vec_list[i] = vec
        return vec_list

    #############################
    # 公共函数
    #############################

    def load_common_para(self):
        """
        装载common_para参数到内存
        """
        _para_dict = dict()
        _query = CommonPara.select(CommonPara.para_name, CommonPara.para_value)
        for _row in _query:
            _para_dict[_row.para_name] = _row.para_value

        # 更新内存
        self.DATA_MANAGER_PARA['common_para'].update(_para_dict)
        self._log_debug('Load common_para success:\n%s' % str(_para_dict))

    def load_nlp_sure_judge_dict(self):
        """
        加载肯定/否定判断字典
        """
        _judge_dict = dict()
        _query = NlpSureJudgeDict.select()
        for _row in _query:
            _judge_dict.setdefault(_row.sign, {})
            _judge_dict[_row.sign].setdefault(_row.word_class, [])
            _judge_dict[_row.sign][_row.word_class].append(_row.word)

        # 添加到内存
        self.DATA_MANAGER_PARA['nlp_sure_judge_dict'] = _judge_dict
        self._log_debug('Load nlp_sure_judge_dict success:\n%s' % str(_judge_dict))

    def load_nlp_purpos_config_dict(self):
        """
        加载意图匹配字典
        """
        _pupos_config = dict()
        _query = NlpPurposConfigDict.select()
        for _row in _query:
            _collection = _row.collection if _row.collection is not None and _row.collection != '' else None
            _partition = _row.partition if _row.partition is not None and _row.partition != '' else None
            _pupos_config.setdefault(_collection, {})
            _pupos_config[_collection].setdefault(_partition, {})
            _pupos_config[_collection][_partition][_row.action] = {
                'order_num': _row.order_num,
                'std_question_id': _row.std_question_id,
                'info': eval('[]' if _row.info == '' else _row.info)
            }

        # 添加到内存
        self.DATA_MANAGER_PARA['nlp_purpos_config_dict'] = _pupos_config
        self._log_debug('Load nlp_purpos_config_dict success:\n%s' % str(_pupos_config))

    def add_collection(self, collection: str, order_num: int = 0, remark: str = ''):
        """
        新增问题分类

        @param {str} collection - 要新增的问题分类
        @param {int} order_num=0 - 顺序号, 越大越优先
        @param {str} remark='' - 备注信息
        """
        with self.get_milvus() as _milvus:
            self._add_collection(collection, _milvus, order_num, remark)

    def delete_collection(self, collection: str, with_question: bool = False):
        """
        删除问题分类

        @param {str} collection - 要删除的问题分类
        @param {bool} with_question=False - 是否同时删除对应的问题
        """
        pass

    def switch_collection_order(self, collection_a: str, collection_b: str):
        """
        交换两个问题分类的顺序位置

        @param {str} collection_a - 问题分类a
        @param {str} collection_b - 问题分类b
        """
        _row_a = CollectionOrder.get(CollectionOrder.collection == collection_a)
        _row_b = CollectionOrder.get(CollectionOrder.collection == collection_b)

        # 交换序号
        _order_num_b = _row_b.order_num
        _row_b.order_num = _row_a.order_num
        _row_a.order_num = _order_num_b

        # 更新
        _row_a.save()
        _row_b.save()

    def query_collection_page_list(self, page: int = 1, page_size: int = 20,
                                   select_fields: tuple = None,
                                   where_expressions: tuple = None,
                                   order_by_values: tuple = None):
        """
        分页查询问题分类清单

        @param {int} page=1 - 分页第几页，从1开始
        @param {int} page_size=20 - 每页记录数量
        @param {tuple} select_fields=None - peewee库select的输入参数，例如:
            (CollectionOrder.collection, CollectionOrder.order_num)
        @param {tuple} where_expressions=None - peewee库where的输入参数，例如:
            (CollectionOrder.order_num >= 10, )
        @param {tuple} order_by_values=None - peewee库order_by的输入参数，例如:
            (CollectionOrder.order_num.desc(), )

        @returns {dict} - 返回结果字典，格式如下：
            {
                'total': int,  # 总记录数
                'total_page': int,  # 总页数
                'page': int,  # 当前页
                'page_size': int,  # 每页大小
                'header': list,  # 表头字段名列表
                'rows': list  # 行记录，每行为一个数据列表，与header位置匹配
            }
        """
        # 返回值
        _result = {
            'total': 0,
            'total_page': 0,
            'page': page,
            'page_size': page_size,
            'header': list(),
            'rows': list()
        }

        # 先组成查询语句
        _query_sql = CollectionOrder.select(*(tuple() if select_fields is None else select_fields))

        if where_expressions is not None:
            _query_sql = _query_sql.where(*where_expressions)

        if order_by_values is not None:
            _query_sql = _query_sql.order_by(*order_by_values)

        # 计算列表总数
        self._log_debug('execute count sql: %s' % str(_query_sql.sql()))

        _result['total'] = _query_sql.count()
        _result['total_page'] = math.ceil(_result['total'] / page_size)

        # 分页处理
        _query_sql = _query_sql.paginate(page, page_size)

        # 组成header
        for _col in _query_sql._returning:
            _result['header'].append(_col.column_name)

        self._log_debug('execute sql: %s' % str(_query_sql.sql()))

        # 查询并组成rows
        for _row in _query_sql.tuples():
            _result['rows'].append(_row)

        # 返回结果
        self._log_debug('returns: %s' % str(_result))

        return _result

    def add_std_question(self, question: str, collection: str = 'chat', q_type: str = 'ask',
                         partition: str = None, answer: str = None, a_type: str = 'text', a_type_param: str = '') -> int:
        """
        添加标准问题

        @param {str} question - 标准问题
        @param {str} collection='chat' - 问题分类，默认为'chat', 可以自定义分类
        @param {str} q_type='ask' - 问题类型
            ask-问答类（问题对应答案）
            context-场景类（问题对应上下文场景）
        @param {str} partition=None - 问题所属场景, q_type为context时使用
        @param {str} answer=None - 标准问题对应的答案
        @param {string} a_type='text' - 答案类型
            text-文字答案
        @param {string} a_type_param='' - 答案类型扩展参数
        @returns {int} - 返回问题记录对应的id
        """
        # 简单校验
        if q_type == 'ask' and answer is None:
            raise AttributeError('parameter answer should be not None!')

        # 获取问题的向量值
        with self.get_bert_client() as _bert, self.get_milvus() as _milvus:
            _vectors = _bert.encode([question, ])
            _question_vectors = self.normaliz_vec(_vectors.tolist())
            self._log_debug('get question vectors: %s' % str(_question_vectors))

            # 存入Milvus服务, 先创建分类
            self._add_collection(collection, _milvus)

            # 创建场景
            if partition is not None and partition != '':
                self._add_partition(collection, partition, _milvus)
            else:
                partition = None

            _milvus_id = self._add_milvus_question(
                _question_vectors[0], collection, partition, _milvus
            )

        # 存入AnswerDb，通过事务处理
        with self.database.atomic() as _txn:
            # 插入标准问题
            _std_q = StdQuestion.create(
                q_type=q_type, milvus_id=_milvus_id, collection=collection,
                partition=('' if partition is None else partition),
                question=question
            )

            # 插入对应的答案
            if answer is not None:
                Answer.create(
                    std_question_id=_std_q.id, a_type=a_type,
                    type_param=a_type_param, answer=answer
                )

            # 提交事务
            _txn.commit()

        # 返回结果
        self._log_debug('insert question: %s' % str(_std_q))
        return _std_q.id

    def add_ext_question(self, std_question_id: int, question: str) -> int:
        """
        添加扩展问题（标准问题的其他问法）

        @param {int} std_question_id - 标准问题记录ID
        @param {str} question - 扩展问题描述

        @returns {int} - 返回记录id
        """
        # 校验标准问题是否存在
        _std_q = StdQuestion.get_or_none(StdQuestion.id == std_question_id)
        if _std_q is None:
            raise AttributeError(
                'parameter std_question_id error: StdQuestion has not id [%d]' % std_question_id)

        # 获取问题的向量值
        with self.get_bert_client() as _bert:
            _vectors = _bert.encode([question, ])
            _question_vectors = self.normaliz_vec(_vectors.tolist())
            self._log_debug('get question vectors: %s' % str(_question_vectors))

        # 存入Milvus服务
        with self.get_milvus() as _milvus:
            _milvus_id = self._add_milvus_question(
                _question_vectors[0], _std_q.collection,
                None if _std_q.partition == '' else _std_q.partition,
                _milvus
            )

        # 存入AnswerDb
        _ext_q = ExtQuestion.create(
            milvus_id=_milvus_id, std_question_id=std_question_id,
            question=question
        )

        # 返回结果
        self._log_debug('insert question: %s' % str(_ext_q))
        return _ext_q.id

    def import_questions_by_xls(self, file_path: str, reset_questions: bool = False):
        """
        通过Excel文件导入问题组

        @param {str} file_path - 文件路径
        @param {bool} reset_questions=False - 是否重置问题库（删除所有问题数据）
        """
        with pd.io.excel.ExcelFile(file_path) as _excel_io, self.get_milvus() as _milvus, self.get_bert_client() as _bert:
            # 重置数据库
            if reset_questions:
                self.truncate_all_questions()

            # 处理Collections
            self._import_collections_by_xls(_excel_io, _milvus, _bert)

            # 处理StdQuestions
            _std_question_id_mapping = self._import_std_questions_by_xls(
                _excel_io, _milvus, _bert)

            # 处理Answers
            self._import_answers_by_xls(_excel_io, _milvus, _bert, _std_question_id_mapping)

            # 处理ExtQuestions
            self._import_ext_questions_by_xls(_excel_io, _milvus, _bert, _std_question_id_mapping)

            # 处理CommonPara
            self._import_common_para_by_xls(_excel_io, _milvus, _bert)

            # 处理NlpSureJudgeDict
            self._import_nlp_sure_judge_dict_by_xls(_excel_io, _milvus, _bert)

            # 处理NlpPurposConfigDict
            self._import_nlp_purpos_config_dict_by_xls(
                _excel_io, _milvus, _bert, _std_question_id_mapping)

    def truncate_all_questions(self):
        """
        清空所有问题组(慎用)
        """
        # 先清空所有问题分类
        with self.get_milvus() as _milvus:
            for _collection in self.sorted_collection:
                _status, _exists = _milvus.has_collection(_collection)
                self.confirm_milvus_status(_status, 'has_collection')
                if _exists:
                    self.confirm_milvus_status(
                        _milvus.drop_collection(_collection), 'drop_collection'
                    )

        # 等待5秒删除
        time.sleep(5)

        # 重建所有数据表（相当于清除数据）
        AnswerDao.drop_tables(ANSWERDB_TABLES)
        AnswerDao.create_tables(ANSWERDB_TABLES)

        # 清空清单
        self.sorted_collection = list()
        self._log_info('truncate_all_questions suceess!')

    def delete_milvus_collection(self, collections: list = [], truncate: bool = False):
        """
        删除Milvus服务的问题分类

        @param {list} collections=[] - 要删除的问题清单
        @param {bool} truncate=False - 是否删除所有分类
        """
        with self.get_milvus() as _milvus:
            if truncate:
                # 清空所有
                _status, _clist = _milvus.list_collections()
                self.confirm_milvus_status(_status, 'list_collections')
            else:
                # 只清空传入列表
                _clist = []
                for _collection in collections:
                    _status, _exists = _milvus.has_collection(_collection)
                    self.confirm_milvus_status(_status, 'has_collection')
                    if _exists:
                        _clist.append(_collection)

            # 开始清除操作
            for _collection in _clist:
                self.confirm_milvus_status(
                    _milvus.drop_collection(_collection), 'drop_collection'
                )

        # 执行完成
        self._log_info('delete milvus collections %s suceess!' % str(_clist))

    def reset_db(self):
        """
        重置数据库
        """
        # 重建所有数据表（相当于清除数据）
        AnswerDao.drop_tables(ANSWERDB_TABLES)
        AnswerDao.create_tables(ANSWERDB_TABLES)
        self._log_info('reset database suceess!')

    #############################
    # 内部函数
    #############################
    def _get_sorted_collection_list(self) -> list:
        """
        获取已排序的问题分类清单

        @returns {list} - 已排序的问题分类清单
        """
        _sorted_list = list()
        _query = (CollectionOrder
                  .select(CollectionOrder.collection)
                  .order_by(CollectionOrder.order_num.desc()))
        for _row in _query:
            _sorted_list.append(_row.collection)

        return _sorted_list

    def _add_collection(self, collection: str, milvus: mv.Milvus, order_num: int = 0, remark: str = '') -> None:
        """
        添加collection

        @param {str} collection - 问题分类
        @param {mv.Milvus} milvus - Milvus连接对象
        @param {int} order_num=0 - 顺序号, 越大越优先
        @param {str} remark='' - 备注信息
        """
        if collection in self.sorted_collection:
            # 无需再添加
            self._log_debug('collection is exists: %s' % collection)
            return

        # 添加Milvus服务中的分类
        _status, _exists = milvus.has_collection(collection)
        self.confirm_milvus_status(_status, 'has_collection')

        if not _exists:
            # 创建分类
            _param = {
                'collection_name': collection,
                'dimension': self.dimension,
                'index_file_size': self.index_file_size,
                'metric_type': self.metric_type,
            }
            self.confirm_milvus_status(
                milvus.create_collection(_param), 'create_collection'
            )

            self._log_debug('added Milvus collection [%s]' % collection)

            # 创建索引
            _index_param = {'nlist': self.nlist}
            self.confirm_milvus_status(
                milvus.create_index(collection, mv.IndexType.IVF_SQ8, _index_param),
                'create_index'
            )

            self._log_debug('added Milvus collection [%s] index' % collection)

        # 添加AnswerDB数据
        _order_num_match = (CollectionOrder.select()
                            .where(CollectionOrder.order_num == order_num)
                            .count())
        if _order_num_match > 0:
            # 如果顺序号有被占用的情况原来的记录大于当前序号的都要加1
            (CollectionOrder
             .update(order_num=CollectionOrder.order_num + 1)
             .where(CollectionOrder.order_num >= order_num)
             .execute())

        CollectionOrder.insert(
            {'collection': collection, 'order_num': order_num, 'remark': remark}
        ).execute()

        self._log_debug('insert collection [%s] to AnswerDB' % collection)

        # 将分类加入到内存排序队列中
        self.sorted_collection.append(collection)

    def _add_partition(self, collection: str, partition: str, milvus: mv.Milvus) -> None:
        """
        创建场景类

        @param {str} collection - 问题分类
        @param {str} partition - 场景类
        @param {mv.Milvus} milvus - Milvus连接对象
        """
        _status, _exists = milvus.has_partition(collection, partition)
        self.confirm_milvus_status(_status, 'has_partition')
        if not _exists:
            # 创建场景
            self.confirm_milvus_status(
                milvus.create_partition(collection, partition), 'create_partition'
            )

    def _add_milvus_question(self, question_vector, collection: str, partition: str,
                             milvus: mv.Milvus) -> int:
        """
        添加标准问题

        @param {object} question_vector - 问题向量
        @param {str} collection - 问题分类
        @param {str} partition - 场景
        @param {mv.Milvus} milvus - Milvus服务连接对象

        @returns {int} - 返回milvus_id
        """
        _status, _milvus_ids = milvus.insert(
            collection, [question_vector, ], partition_tag=partition)
        self.confirm_milvus_status(_status, 'insert')
        self._log_debug('insert _milvus_ids: %s' % str(_milvus_ids))

        return _milvus_ids[0]

    #############################
    # 数据导入处理相关函数
    #############################

    def _import_collections_by_xls(self, excel_io, milvus: mv.Milvus, bert: BertClient):
        """
        导入Collections

        @param {object} excel_io - pd.io.excel.ExcelFile的IO文件
        @param {Milvus} milvus - Milvus连接对象
        @param {BertClient} bert - bert服务连接对象
        """
        try:
            # 读取文件，第0行为标题行
            _df = pd.read_excel(
                excel_io, sheet_name='Collections', header=0, engine=self.excel_engine
            )
            # 指定所需的列
            _df = _df[['collection', 'order_num', 'remark']]
        except:
            _df = None  # 没有获取到指定的页

        if _df is not None:
            for _index, _row in _df.iterrows():
                # 逐行添加分类集, _index为行，_row为数据集
                self._add_collection(
                    _row['collection'], milvus,
                    order_num=_row['order_num'], remark=_row['remark']
                )

            self._log_debug('imported collection: %s' % str(_df))

    def _import_std_questions_by_xls(self, excel_io, milvus: mv.Milvus, bert: BertClient):
        """
        导入std_questions

        @param {object} excel_io - pd.io.excel.ExcelFile的IO文件
        @param {Milvus} milvus - Milvus连接对象
        @param {BertClient} bert - bert服务连接对象

        @ return {dict} - 标准问题id映射字典
        """
        _std_question_id_mapping = dict()  # 标准问题excel上的id和真实id的映射关系
        try:
            # 读取标题行
            _df_header = pd.read_excel(
                excel_io, sheet_name='StdQuestions', nrows=0, engine=self.excel_engine
            )
        except:
            _df_header = None  # 没有获取到指定的页

        if _df_header is not None:
            _skiprows = 1  # 跳过的记录数
            _columns = {i: col for i, col in enumerate(_df_header.columns.tolist())}
            while True:
                # 循环处理
                _df = pd.read_excel(
                    excel_io, sheet_name='StdQuestions', nrows=self.excel_batch_num,
                    header=None, skiprows=_skiprows, engine=self.excel_engine
                )
                _skiprows += self.excel_batch_num

                if not _df.shape[0]:
                    # 获取不到数据
                    break

                # 变更标题
                _df.rename(columns=_columns, inplace=True)

                # 批量处理问题分类
                _array_collection = np.unique(_df['collection'].values).tolist()
                for _collection in _array_collection:
                    self._add_collection(_collection, milvus)

                # 批量处理场景, 去除nan的值
                _array_partition = [
                    x for x in _df[['collection', 'partition']].values if str(x[1]) != 'nan'
                ]
                _array_partition = list(set([tuple(t) for t in _array_partition]))  # 二维去重
                for _partition in _array_partition:
                    self._add_partition(_partition[0], _partition[1], milvus)

                # 批量生成向量
                _vectors = bert.encode(_df['question'].values.tolist())
                _question_vectors = self.normaliz_vec(_vectors.tolist())
                self._log_debug('get std_questions[%d] bert vectors, count: %s' % (
                    _skiprows, str(len(_question_vectors))))

                for _index, _row in _df.iterrows():
                    # 逐行添加标准问题, _index为行，_row为数据集
                    _partition = _row['partition'] if str(
                        _row['partition']) != 'nan' and _row['partition'] != '' else None

                    if str(_row['milvus_id']) == 'nan':
                        _milvus_id = self._add_milvus_question(
                            _question_vectors[_index], _row['collection'],
                            _partition, milvus
                        )
                    else:
                        _milvus_id = int(_row['milvus_id'])

                    # 插入标准问题
                    _std_q = StdQuestion.create(
                        q_type=_row['q_type'], milvus_id=_milvus_id, collection=_row['collection'],
                        partition=('' if _partition is None else _partition),
                        question=_row['question']
                    )

                    # 插入映射关系
                    if str(_row['id']) != 'nan':
                        _std_question_id_mapping[_row['id']] = _std_q.id

                self._log_debug('imported std_question[%d]: %s' % (_skiprows, str(_df)))

        # 返回映射
        return _std_question_id_mapping

    def _import_answers_by_xls(self, excel_io, milvus: mv.Milvus, bert: BertClient,
                               std_question_id_mapping: dict):
        """
        导入Answers

        @param {object} excel_io - pd.io.excel.ExcelFile的IO文件
        @param {Milvus} milvus - Milvus连接对象
        @param {BertClient} bert - bert服务连接对象
        @param {dict} std_question_id_mapping - 标准问题id映射字典
        """
        try:
            # 读取标题行
            _df_header = pd.read_excel(
                excel_io, sheet_name='Answers', nrows=0, engine=self.excel_engine
            )
        except:
            _df_header = None  # 没有获取到指定的页

        if _df_header is not None:
            # 定义替换变量函数
            def replace_var_fun(m):
                _match_str = m.group(0)
                if _match_str.startswith('{$id='):
                    # 替换为映射id
                    _id: str = _match_str[5: -2]
                    if _id.isdigit():
                        # 是数字
                        _new_id = std_question_id_mapping.get(
                            int(_id), _id
                        )
                    else:
                        # 是字符串
                        _new_id = std_question_id_mapping.get(
                            _id, _id
                        )
                    return str(_new_id)

                # 没有匹配到
                return _match_str

            _skiprows = 1  # 跳过的记录数
            _columns = {i: col for i, col in enumerate(_df_header.columns.tolist())}
            while True:
                # 循环处理
                _df = pd.read_excel(
                    excel_io, sheet_name='Answers', nrows=self.excel_batch_num,
                    header=None, skiprows=_skiprows, engine=self.excel_engine
                )
                _skiprows += self.excel_batch_num

                if not _df.shape[0]:
                    # 获取不到数据
                    break

                # 变更标题
                _df.rename(columns=_columns, inplace=True)

                for _index, _row in _df.iterrows():
                    # 逐行添加标准问题答案, _index为行，_row为数据集
                    _std_question_id = std_question_id_mapping.get(
                        _row['std_question_id'], _row['std_question_id']
                    )
                    _type_param = re.sub(
                        r'\{\$.+?\$\}', replace_var_fun, str(_row['type_param']), re.M
                    )
                    Answer.create(
                        std_question_id=_std_question_id, a_type=_row['a_type'],
                        type_param=_type_param, replace_pre_def=_row['replace_pre_def'],
                        answer=_row['answer']
                    )

                self._log_debug('imported answers[%d]: %s' % (_skiprows, str(_df)))

    def _import_ext_questions_by_xls(self, excel_io, milvus: mv.Milvus, bert: BertClient,
                                     std_question_id_mapping: dict):
        """
        导入ExtQuestions

        @param {object} excel_io - pd.io.excel.ExcelFile的IO文件
        @param {Milvus} milvus - Milvus连接对象
        @param {BertClient} bert - bert服务连接对象
        @param {dict} std_question_id_mapping - 标准问题id映射字典
        """
        try:
            # 读取标题行
            _df_header = pd.read_excel(
                excel_io, sheet_name='ExtQuestions', nrows=0, engine=self.excel_engine
            )
        except:
            _df_header = None  # 没有获取到指定的页

        if _df_header is not None:
            _skiprows = 1  # 跳过的记录数
            _columns = {i: col for i, col in enumerate(_df_header.columns.tolist())}
            while True:
                # 循环处理
                _df = pd.read_excel(
                    excel_io, sheet_name='ExtQuestions', nrows=self.excel_batch_num,
                    header=None, skiprows=_skiprows, engine=self.excel_engine
                )
                _skiprows += self.excel_batch_num

                if not _df.shape[0]:
                    # 获取不到数据
                    break

                # 变更标题
                _df.rename(columns=_columns, inplace=True)

                # 批量生成向量
                _vectors = bert.encode(_df['question'].values.tolist())
                _question_vectors = self.normaliz_vec(_vectors.tolist())
                self._log_debug('get ext_questions[%d] bert vectors count: %s' % (
                    _skiprows, str(len(_question_vectors))))

                for _index, _row in _df.iterrows():
                    # 逐行添加扩展问题, _index为行，_row为数据集
                    _std_question_id = std_question_id_mapping.get(
                        _row['std_question_id'], _row['std_question_id']
                    )
                    _std_q = StdQuestion.get_or_none(StdQuestion.id == _std_question_id)

                    _milvus_id = self._add_milvus_question(
                        _question_vectors[_index], _std_q.collection,
                        None if _std_q.partition == '' else _std_q.partition,
                        milvus
                    )

                    ExtQuestion.create(
                        milvus_id=_milvus_id, std_question_id=_std_question_id,
                        question=_row['question']
                    )

                self._log_debug('imported ext_questions[%d]: %s' % (_skiprows, str(_df)))

    def _import_common_para_by_xls(self, excel_io, milvus: mv.Milvus, bert: BertClient):
        """
        导入CommonPara

        @param {object} excel_io - pd.io.excel.ExcelFile的IO文件
        @param {Milvus} milvus - Milvus连接对象
        @param {BertClient} bert - bert服务连接对象
        """
        try:
            # 读取文件，第0行为标题行
            _df = pd.read_excel(
                excel_io, sheet_name='CommonPara', header=0, engine=self.excel_engine
            )
            # 指定所需的列
            _df = _df[['para_name', 'para_value', 'remark']]
        except:
            _df = None  # 没有获取到指定的页

        if _df is not None:
            for _index, _row in _df.iterrows():
                # 逐行添加, _index为行，_row为数据集
                CommonPara.create(
                    para_name=_row['para_name'], para_value=_row['para_value'],
                    remark=_row['remark']
                )

            # 导入后重新加载到内存
            self.load_common_para()

            self._log_debug('imported common_para: %s' % str(_df))

    def _import_nlp_sure_judge_dict_by_xls(self, excel_io, milvus: mv.Milvus, bert: BertClient):
        """
        装载NlpSureJudgeDict

        @param {object} excel_io - pd.io.excel.ExcelFile的IO文件
        @param {Milvus} milvus - Milvus连接对象
        @param {BertClient} bert - bert服务连接对象
        """
        try:
            # 读取文件，第0行为标题行
            _df = pd.read_excel(
                excel_io, sheet_name='NlpSureJudgeDict', header=0, engine=self.excel_engine
            )
            # 指定所需的列
            _df = _df[['word', 'sign', 'word_class']]
        except:
            _df = None  # 没有获取到指定的页

        if _df is not None:
            for _index, _row in _df.iterrows():
                # 逐行添加, _index为行，_row为数据集
                NlpSureJudgeDict.create(
                    word=_row['word'], sign=_row['sign'], word_class=_row['word_class']
                )

            # 导入后重新加载到内存
            self.load_nlp_sure_judge_dict()

            self._log_debug('imported nlp_purpos_config_dict: %s' % str(_df))

    def _import_nlp_purpos_config_dict_by_xls(self, excel_io, milvus: mv.Milvus, bert: BertClient,
                                              std_question_id_mapping: dict):
        """
        导入NlpPurposConfigDict

        @param {object} excel_io - pd.io.excel.ExcelFile的IO文件
        @param {Milvus} milvus - Milvus连接对象
        @param {BertClient} bert - bert服务连接对象
        @param {dict} std_question_id_mapping - 标准问题id映射字典
        """
        try:
            # 读取标题行
            _df_header = pd.read_excel(
                excel_io, sheet_name='NlpPurposConfigDict', nrows=0, engine=self.excel_engine
            )
        except:
            _df_header = None  # 没有获取到指定的页

        if _df_header is not None:
            # 定义替换变量函数
            def replace_var_fun(m):
                _match_str = m.group(0)
                if _match_str.startswith('{$id='):
                    # 替换为映射id
                    _id: str = _match_str[5: -2]
                    if _id.isdigit():
                        # 是数字
                        _new_id = std_question_id_mapping.get(
                            int(_id), _id
                        )
                    else:
                        # 是字符串
                        _new_id = std_question_id_mapping.get(
                            _id, _id
                        )
                    return str(_new_id)

                # 没有匹配到
                return _match_str

            _skiprows = 1  # 跳过的记录数
            _columns = {i: col for i, col in enumerate(_df_header.columns.tolist())}
            while True:
                # 循环处理
                _df = pd.read_excel(
                    excel_io, sheet_name='NlpPurposConfigDict', nrows=self.excel_batch_num,
                    header=None, skiprows=_skiprows, engine=self.excel_engine
                )
                _skiprows += self.excel_batch_num

                if not _df.shape[0]:
                    # 获取不到数据
                    break

                # 变更标题
                _df.rename(columns=_columns, inplace=True)

                for _index, _row in _df.iterrows():
                    # 逐行添加标准问题答案, _index为行，_row为数据集
                    _collection = _row['collection'] if str(
                        _row['collection']) != 'nan' and _row['collection'] != '' else None

                    _partition = _row['partition'] if str(
                        _row['partition']) != 'nan' and _row['partition'] != '' else None

                    _std_question_id = std_question_id_mapping.get(
                        _row['std_question_id'], _row['std_question_id']
                    )

                    _info = _row['info'] if str(
                        _row['info']) != 'nan' and _row['info'] != '' else '[]'
                    _info = re.sub(
                        r'\{\$.+?\$\}', replace_var_fun, _info, re.M
                    )

                    NlpPurposConfigDict.create(
                        action=_row['action'],
                        collection=_collection,
                        partition=('' if _partition is None else _partition),
                        std_question_id=_std_question_id,
                        order_num=_row['order_num'],
                        info=_info
                    )

                # 加载到内存
                self.load_nlp_purpos_config_dict()

                self._log_debug('imported nlp_purpos_config_dict[%d]: %s' % (_skiprows, str(_df)))

    #############################
    # 日志输出相关函数
    #############################
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
