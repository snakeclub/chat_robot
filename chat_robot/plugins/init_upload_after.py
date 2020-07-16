#!/usr/bin/env python2
# -*- coding: UTF-8 -*-
# Copyright 2019 黎慧剑
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
初始化上传后处理插件函数
@module init_upload_after
@file init_upload_after.py
"""

import os
import sys
import re
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))


__MOUDLE__ = 'init_upload_after'  # 模块名
__DESCRIPT__ = u'初始化上传后处理插件函数'  # 模块描述
__VERSION__ = '0.1.0'  # 版本
__AUTHOR__ = u'黎慧剑'  # 作者
__PUBLISH__ = '2020.07.11'  # 发布日期


class InitUploadAfter(object):
    """
    上传后处理插件函数
    """
    @classmethod
    def plugin_type(cls):
        """
        必须定义的函数，返回插件类型
        """
        return 'upload_after'

    @classmethod
    def initialize(cls, loader, qa_manager, qa, **kwargs):
        """
        装载插件前执行的初始化处理
        可以不定义

        @param {QAServerLoader} loader - 服务装载器
        @param {QAManager} qa_manager - 数据管理
        @param {QA} qa - 问答服务
        """
        pass

    @classmethod
    def test(cls, upload_type: str, note: str, file_name: str, save_path: str, url: str, **kwargs):
        """
        测试函数

        @param {str} upload_type - 文件类型，必须在UploadFileConfig表中有配置
        @param {str} note - 文件注解
        @param {str} file_name - 保存的文件名
        @param {str} save_path - 保存的文件路径(含文件名)
        @param {str} url - 可访问的url

        @returns {str, str, list} - 返回处理结果二元组 status, msg, answers
            注：可以通过这个返回改变上传成功的结果，answers是返回的回答字符数组，如果不许需要回答则应可返回[]
        """
        return '00000', 'success', ['文件上传成功: %s' % url]


if __name__ == '__main__':
    # 当程序自己独立运行时执行的操作
    # 打印版本信息
    print(('模块名：%s  -  %s\n'
           '作者：%s\n'
           '发布日期：%s\n'
           '版本：%s' % (__MOUDLE__, __DESCRIPT__, __AUTHOR__, __PUBLISH__, __VERSION__)))
