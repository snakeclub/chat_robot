#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
测试
@module test
@file test.py
"""

import os
import sys
from HiveNetLib.base_tools.file_tool import FileTool
from HiveNetLib.simple_xml import SimpleXml
# 根据当前文件路径将包路径纳入，在非安装的情况下可以引用到
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir)))
from chat_robot.lib.data_manager import QAManager
from chat_robot.lib.qa import QA
from chat_robot.lib.loader import QAServerLoader

# 数据管理模块
_file_path = os.path.realpath(FileTool.get_file_path(__file__))
_execute_path = os.path.join(_file_path, os.path.pardir, 'chat_robot')
# _config = os.path.join(_execute_path, os.path.pardir, 'chat_robot/conf/server.xml')
_config = os.path.join(_execute_path, './conf/server.xml')
_config_xml = SimpleXml(_config, encoding='utf-8')
SERVER_CONFIG = _config_xml.to_dict()['server']
SERVER_CONFIG['debug'] = True
SERVER_CONFIG['config'] = _config
SERVER_CONFIG['encoding'] = 'utf-8'
SERVER_CONFIG['execute_path'] = _execute_path


# 装载服务
_loader = QAServerLoader(SERVER_CONFIG)


_qa_manager: QAManager = _loader.qa_manager

# 导入Excel数据
# _qa_manager.import_questions_by_xls(
#     os.path.join(_execute_path, '../test/questions.xlsx'), reset_questions=True
# )

# 初始化QA模块
_qa: QA = _loader.qa

# 创建用户session
_session_id = _qa.generate_session({
    'name': '测试用户',
})

# 测试问答
# _question = '你好'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '您好'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '你好啊'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '这个问题应该不存在才对啊'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '[选项]我想学银行业务'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '4'  # 超过选项范围，继续提问
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '2'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '1'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '[选项]我想学银行业务'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '你叫什么名字'  # 选项中输入其他问题，跳出选项上下文
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '1'  # 已跳出选项不再匹配
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '[选项]我想学银行业务'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '3'  # 二级选项
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '1'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '[未精确匹配]90%以上'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '1'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '[job示例]获取随机答案'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '[job示例]获取随机答案'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '不应该匹配到的随机答案3'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '[ask示例]问我的名字'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '黎慧剑'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '[ask示例]重复提问'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '继续'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '1'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '[ask示例1]单问题多轮提问'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '18岁'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '男'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '[ask示例2]多个问题多轮提问'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '广州'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '搬砖'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '篮球'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '我要寄信给广州的黎慧剑'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '我要转账'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '黎慧剑'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '500'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '是的'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '我要转账给黎慧剑的账户315元'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '不是'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '广州的天气'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '明天广州的天气'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '朝阳的天气'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '3'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '2'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '朝阳的天气'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '不是吧'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '今天天气怎么样？'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

# _question = '今天天气真好'
# print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

_question = '你叫什么名字'
print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

_question = '翡翠'
print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

_question = '翡翠是怎么形成的'
print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

_question = '继续'
print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

_question = '下一个'
print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

_question = '帮助'
print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

_question = '你叫什么名字？'
print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))

_question = '你叫什么名字？'
print(_question, ' : ', _qa.quession_search(_question, session_id=_session_id))
