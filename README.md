# chat_robot说明
chat robot 是一个机器人对话框架，可以实现闲聊、客服问答、知识库检索等基于对话的场景应用，其基本原理是基于**BERT模型（Bidirectional Encoder Representation from Transformers）**对标准问题生成语义相似度向量并存入到**Milvus**服务中，利用**Milvus**服务快速实现客户输入问题的相似度向量的检索匹配，并返回对应的答案；此外也通过开源项目**Jieba**的NLP分词功能对语句进行分词和意图动作匹配，实现部分特殊动作的识别处理。

chat robot框架可以支持进行job、ask、options等对话插件的开发和导入，便于扩展实现各种特殊场景的对话处理。



# 安装手册

## 安装依赖服务

### 安装Bert服务

开源项目地址：https://github.com/hanxiao/bert-as-service

使用的谷歌的BERT预训练模型，也可以使用国内针对中文全词遮罩技术的模型（推荐）：

谷歌项目：https://github.com/google-research/bert

模型下载地址：https://storage.googleapis.com/bert_models/2018_11_03/chinese_L-12_H-768_A-12.zip

基于全词遮罩（Whole Word Masking）技术（推荐）：https://github.com/ymcui/Chinese-BERT-wwm

模型下载地址：https://pan.iflytek.com/link/653637473FFF242C3869D77026C9BDB5  密码4cMG

步骤如下

1、服务器上安装bert-serving-server库

```
$ pip install -i https://pypi.tuna.tsinghua.edu.cn/simple bert-serving-server
```

2、下载BERT预训练模型，建议下载全词遮罩（Whole Word Masking）的模型，文件为：chinese_wwm_ext_L-12_H-768_A-12.zip

3、解压缩模型到服务器上，指定模型解压后的目录，启动服务：

```
$ cd /home/ubuntu18/milvus/model/chinese_wwm_ext_L-12_H-768_A-12
$ nohup bert-serving-start -model_dir /home/ubuntu18/milvus/model/chinese_wwm_ext_L-12_H-768_A-12 -num_worker=12 -max_seq_len=40 &
```

启动后默认服务的端口为5555和5556，如果需要改变服务端口，可以在启动命令上增加port和port_out参数进行指定。



### 安装Milvus服务

详细安装材料可参考官网文档：https://milvus.io/cn/docs/v0.10.0/guides/get_started/install_milvus/cpu_milvus_docker.md

建议采用docker方式进行安装（注意要求docker版本19.03以上），具体步骤如下：

1、通过docker pull获取docker镜像

```
sudo docker pull milvusdb/milvus:0.10.0-cpu-d061620-5f3c00
```

注:  安装过程可能会遇到以下问题，可参考以下解决方案

（1）docker pull中间取消后，重新获取出现“Repository milvusdb/milvus already being pulled by another client. Waiting.”错误，该问题是一个bug，可以通过重启docker方法解决：

```
sudo service docker stop
sudo service docker start
```

2、下载配置文件

```
$ mkdir -p /home/ubuntu18/milvus/conf
$ cd /home/ubuntu18/milvus/conf
$ wget https://raw.githubusercontent.com/milvus-io/milvus/v0.10.0/core/conf/demo/server_config.yaml
```

注：如果下载不了，可自行编辑创建该配置文件

3、启动容器

```
$ sudo docker run -d --name milvus_cpu_0.10.0 \
-p 19530:19530 \
-p 19121:19121 \
-v /home/ubuntu18/milvus/db:/var/lib/milvus/db \
-v /home/ubuntu18/milvus/conf:/var/lib/milvus/conf \
-v /home/ubuntu18/milvus/logs:/var/lib/milvus/logs \
-v /home/ubuntu18/milvus/wal:/var/lib/milvus/wal \
milvusdb/milvus:0.10.0-cpu-d061620-5f3c00
```

上述命令中用到的 `docker run` 参数定义如下：

- `-d`: 运行 container 到后台并打印 container id。
- `--name`: 为 container 分配一个名字。
- `-p`: 暴露 container 端口到 host。
- `-v`: 将路径挂载至 container。

4、确认 Milvus 运行状态

```
$ docker ps
```

如果docker没有正常启动，可以执行以下命令查看错误日志：

```
 # 获得运行 Milvus 的 container ID。
 $ docker ps -a
 # 检查 docker 日志。
 $ docker logs <milvus container id>
```



### 安装MySQL

本项目使用MySql 5.7作为持久化数据库，该数据库既可以作为Milvus的数据库，也可以作为chat_robot应用的数据库使用，当然你也可以使用两个独立的数据库分别部署。

1、通过docker安装数据库

```
# 获取镜像
$ sudo docker pull mysql:5.7
```

2、自定义数据库的启动参数

```
# 创建本地目录
mkdir -p /home/ubuntu18/milvus/mysql/conf /home/ubuntu18/milvus/mysql/logs /home/ubuntu18/milvus/mysql/data

# 启动镜像
$ docker run -p 3306:3306 --name mysql5.7 -e MYSQL_ROOT_PASSWORD=123456 -d mysql:5.7

# 获取dockers的容器id (CONTAINER ID)
$ docker ps

# 复制docker默认的mysql配置文件，用于修改成自己的配置文件
$ docker cp 2d1d71afff2f:/etc/mysql/mysql.cnf /home/ubuntu18/milvus/mysql/conf/my.cnf

# 编辑my.cnf
$ vi my.cnf

# 删除临时docker
$ docker stop 2d1d71afff2f
$ docker rm 2d1d71afff2f
```

可以编辑的my.cnf内容如下，按需定制：

```
# 原默认内容
!includedir /etc/mysql/conf.d/
!includedir /etc/mysql/mysql.conf.d/

[client]
#客户端设置
port=3306
default-character-set=utf8mb4

[mysql.server]
default-character-set=utf8mb4

[mysqld_safe]
default-character-set=utf8mb4

[mysqld]
#mysql启动时使用的用户
user=mysql
#默认连接端口
port=3306
#端口绑定的ip地址，0.0.0.0表示允许所有远程访问，127.0.0.1表示只能本机访问，默认值为*
bind-address=0.0.0.0
 
#系统数据库编码设置，排序规则
character_set_server=utf8mb4
collation_server=utf8mb4_bin
 
#secure_auth 为了防止低版本的MySQL客户端(<4.1)使用旧的密码认证方式访问高版本的服务器。MySQL 5.6.7开始secure_auth 默认为启用值1
secure_auth=1
 
#linux下要严格区分大小写，windows下不区分大小写
#1表示不区分大小写，0表示区分大小写。
lower_case_table_names=0
```

3、启动正式的镜像

```
# 启动镜像
$ docker run -p 3306:3306 --name milvusdb \
-v /home/ubuntu18/milvus/mysql/conf/my.cnf:/etc/mysql/my.cnf \
-v /home/ubuntu18/milvus/mysql/data:/var/lib/mysql \
-v /home/ubuntu18/milvus/mysql/logs:/var/log/mysql \
-e MYSQL_ROOT_PASSWORD=123456 -d mysql:5.7

# 进入mysql的容器命令行
$ docker exec -ti milvusdb bash

# 登陆
mysql -uroot -p123456

# 开启远程连接
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' IDENTIFIED BY '123456' WITH GRANT OPTION;
FLUSH PRIVILEGES;

# 创建数据库
create database milvus;

# 退出
exit;
```

4、修改Milvus服务的配置文件`server_config.yaml` 

```
# 查找docker宿主机的访问IP地址
$ ip addr show docker0
3: docker0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether 56:84:7a:fe:97:99 brd ff:ff:ff:ff:ff:ff
    inet 172.17.42.1/16 scope global docker0
       valid_lft forever preferred_lft forever
    inet6 fe80::5484:7aff:fefe:9799/64 scope link 
       valid_lft forever preferred_lft forever

$ vi /home/ubuntu18/milvus/conf/server_config.yaml
```

将meta_uri参数修改为（注意IP地址）：

```
meta_uri: mysql://root:123456@172.17.42.1:3306/milvus
```

5、重启milvus服务

```
$ docker restart milvus_cpu_0.10.0
```



### 安装Redis

Redis作为chat_robot的缓存数据库，用于缓存session数据及一些插件的临时数据，这是一个可选项，如果你的应用只需要支持单机部署且不需要使用缓存的插件，可以选择不使用Redis，但如果需要支持分布式部署，则必须安装Redis用于缓存数据的共享。

1、获取Redis的Docker镜像

```
$ docker pull redis:latest
```

最新的版本应该是6.0.5，以下示例的配置以6.0.5为准，如果不确定可以使用以下方式确认镜像的版本：

```
# 创建一个测试docker
$ docker run -d -p 6379:6379 --name redis_test redis redis-server --appendonly yes

# 进入docker
$ docker exec -ti redis_test bash

# 执行以下命令查看服务器和客户端版本
$ redis-server -v
Redis server v=6.0.5 sha=00000000:0 malloc=jemalloc-5.1.0 bits=64 build=db63ea56716d515f

$ redis-cli -v
redis-cli 6.0.5

# 删除临时的测试容器
$ docker stop redis_test
$ docker rm redis_test
```

2、获取redis的配置文件并进行修改，可以从https://redis.io/上下载最新的源码，在源码根目录上的redis.conf就是默认的配置文件，获取到后我们修改以下几项内容：

```
# 绑定的主机地址
# 你可以绑定单一接口，如果没有绑定，所有接口都会监听到来的连接, 如果需要支持远程访问，需注释该配置
# bind 127.0.0.1

# 如果需要其他主机能访问服务，需要设置为no
protected-mode no

# 使用docker必须将该参数设置为no，否则无法启动容器
daemonize no

# 指定aof等数据文件存储的路径
dir /data

# 否启用aof持久化方式 。即是否在每次更新操作后进行日志记录，默认配置是no，即在采用异步方式把数据写入到磁盘，如果不开启，可能会在断电时导致部分数据丢失
appendonly yes
```

修改后的配置文件可以从 /docs/redis/redis.conf 获取

3、在服务器上建立相应目录，例如：

```
cd /home/ubuntu18/milvus
mkdir redis
mkdir redis/conf
mkdir redis/data
```

然后将配置文件redis.conf复制到 /home/ubuntu18/milvus/redis/conf 目录下

4、启动容器

```
$ docker run -d --privileged=true -p 6379:6379 -v  /home/ubuntu18/milvus/redis/conf/redis.conf:/usr/local/etc/redis/redis.conf -v /home/ubuntu18/milvus/redis/data:/data --name chat_redis redis redis-server /usr/local/etc/redis/redis.conf
```

5、进入容器验证

```
$ docker exec -it chat_redis /bin/bash
root@bb0bc1088bd1:/data# redis-cli
127.0.0.1:6379> set test 1
OK
```



## 安装chat_robot

### 安装及启动应用

注意：chat robot需要使用mysql作为数据库服务器，请在启动前安装好MySQL并建好对应的数据库（可以与Milvus共用数据库实例，通过不同数据库区分即可）

1、将chat robot源码下载到服务器：https://github.com/snakeclub/chat_robot

2、安装依赖包，基于源码目录下的requriment.txt安装清单：

```
$ pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requriment.txt
```

3、按实际环境情况，修改 chat_robot/chat_robot/conf/server.xml的配置信息

4、使用chat_robot/chat_robot/server.py启动问答服务

```
$ python server.py
```

程序将自动找到当前目录下的./conf/server.xml配置文件，如果需要指定其他配置文件，可以在命令中指定配置文件：

```
$ python server.py config="d:/test/server.xml"
```



### 管理问答库数据

默认安装的chat_robot是无法直接处理提问，需要维护问答库数据才能支持问答处理，可以通过 “chat_robot/chat_robot/import.py” 脚本进行问答库的维护。

**1、导入问答库信息**

问答库的导入模板可参考 “chat_robot/test/questions.xlsx” 文件，导入数据的脚本如下：

```
$ python import.py import=../test/questions.xlsx truncate=true
```

注：truncate标志指定清空此前的问答库，如果是增量导入可去掉truncate标志；如果导入的模板中包含NlpSureJudgeDict，NlpPurposConfigDict，则需要重启应用进行加载。

**2、重置数据库（清空所有数据）**

可执行以下命令清空所有数据：

```
$ python import.py del_db=true
```

**3、清空Milvus向量信息**

清除特定的问题分类（collection），多个分类使用 “,” 分隔：

```
$ python import.py del_milvus=test_chat,test_finance
```

清除所有的问题分类（collection），del_milvus传空值：

```
$ python import.py del_milvus= truncate=true
```

**4、指定特定的配置文件获取库信息**

```
$ python import.py config="d:/test/server.xml" import=../test/questions.xlsx truncate=true
```



### 启动测试客户端

可以通过指定 server.xml 配置中的 enable_client 参数，在启动服务时将同步启动测试客户端的页面服务。

启动后可以通过以下地址打开客户端对话页面：http://127.0.0.1:8001/ 

利用该对话页面可以验证对话的结果。

注意：生产部署请勿打开该参数，且注意要删除数据库表 restful_api_user 的测试用户信息。



### 使用Restful Api服务

chat_robot目前仅关注于问答后台服务的实现，并通过Restful Api提供调用的支持，需应用自行实现对话客户端的交互处理，支持的Api服务及传参可直接查看源码文件 “chat_robot/lib/restful_api.py”，主要Api如下：

**TokenServer（服务端为客户端生成可用Token）**

- Api Url：/api/TokenServer/GenerateUserToken
- 用途: 后台服务端为客户端生成可用的令牌用于访问

**AddSendMessage（服务端为向客户发送消息）**

- Api Url：/api/TokenServer/AddSendMessage
- 用途: 后台服务端为向指定客户发送消息，比如系统提示、投诉回复，或者客户之间的消息交互

**GenerateToken（创建Token）**

- Api Url: /api/Qa/GenerateToken
- 用途: 生成可用的安全令牌，客户端可定时重新生成一次新的令牌用于访问

**GetSessionId（获取对话Session ID）**

- Api Url: /api/Qa/GetSessionId
- 用途: 获取本次对话的Session ID，该ID必须每次对话都传入，用于处理上下文内容的传递

**SearchAnswer（获取问题答案）**

- Api Url: /api/Qa/SearchAnswer
- 用途: 输入问题并获取对应的问题答案，可用通过指定特定问题分类，将问题限定在一个范围内匹配答案

**UploadFile（上传文件-单文件）**

- Api Url: /api/Qa/UploadFiles/<upload_type>/<note>/<interface_seq_id>
- 用途: 客户端上传文件，进行文件上传后处理并返回处理结果

**GetMessageCount（获取当前客户的待收消息数量-平台推送）**

- Api Url: /api/Qa/GetMessageCount
- 用途: 获取当前客户端的待收消息数量，该消息可由平台或其他用户发出，在平台上进行缓存供客户端登陆后获取

**GetMessageList（获取当前客户的待收消息内容清单）**

- Api Url: /api/Qa/GetMessageList
- 用途: 获取当前客户端的待收消息内容清单，每次可获取的消息数量由服务器端控制，可通过 server.xml 配置中的 query_send_message_num 参数控制；需注意该API并不会删除客户服务端的缓存记录，应通过 ConfirmMessageList 进行获取消息的确认并删除

**ConfirmMessageList（确认已收到客户消息）**

- Api Url: /api/Qa/ConfirmMessageList
- 用途: 客户端正常收取到待收消息后，通过该接口确认消息已收到，服务端才将消息从代收队列中删除



# 通讯安全机制

**不支持HTTPS**

chat_robot采用的是http协议进行交互，暂未支持https，如需使用https可使用Nginx等Web代理实现SSL校验和解SSL。

**Token（令牌）的使用**

在访问限制方面，chat_robot使用token（令牌）技术进行接口访问权限的限制，token校验的开关及相关参数可在  server.xml 配置中的 security 参数进行设置。

Restful Api 的客户端代码可参考 chat_robot/client/static/index.html 及 chat_robot/client/static/js/functions.js 

**特别注意需要在客户端Http请求的报文头（headers）上增加 UserId 和 Authorization 参数 :**

```
headers: {
    UserId: $.UserId,
    Authorization: 'JWT ' + $.Token
}
```

其中 UserId 为  restful_api_user 表上配置的用户id，Authorization 放置的是与 UserId 对应的令牌字符串（注意令牌前面要加上 “JWT ”），该令牌应该由用户的登陆操作从后台服务产生并发给客户端。

**改变Token校验规则**

如果想自定义Token校验的规则，可用直接修改 “chat_robot/lib/restful_api.py” 中的 “verify_token” 函数。



**生产模式的令牌安全方案**

在生产环境，由对应系统的后台应用直接调用 /api/TokenServer/GenerateUserToken 服务为客户生成临时访问token（传入的user_id是用户登陆后的id，或者一个不会重复的随机id），处理流程如下：

客户打开聊天界面 -> 应用后台调用TokenServer为客户生成令牌 -> 应用后台返回给客户user_id和可用令牌值 -> 聊天客户端使用user_id和令牌调用chat_robot服务 -> 聊天客户端定时生成新的可用令牌

打开TokenServer和变更验证方式，可修改 server.xml 配置中的 security 参数。



# 对话场景支持

chat_robot框架目前支持text、job、ask、options等4种对话场景的处理支持，配置在答案表（a_type字段）分别说明如下：

## text（文字回答）

最简单的问答模式，没有上下文关系，处理流程如下：

收到问题 -> 匹配标准问题 -> 找到问题答案 -> 直接回复答案文本（answer字段）

## options（对话选项）

选项模式的对话，对话过程中需要通过上下文判断，例如客户提问后给客户多个选项，在客户选择具体选项后，返回的是该选项的答案。

一共有两种情况会产生对话选项：

**问题答案设置为选项**

- 设置方法：标准问题答案的a_type字段设置为options，type_param字段设置为选项列表，格式为 “**[ [选项对应标准问题id, '选项提示信息'], ... ]**” ，例如"[ [23, '存款'], [24, '贷款'], [25, '其他'] ]", answer字段设置为选项前的提示内容
- 处理流程：收到问题 -> 匹配到选项问题 -> 将提示和选项组合为答案文本回复 -> 客户回答选项序号 -> 根据上下文找到选项序号对应的选项标准问题ID，执行该标准问题的回答处理
- 跳出条件：如果客户回复的选项序号（数字）不在选项范围，将提示客户重新选择；如果客户回复的是非序号，则认为客户提出了新问题，直接跳出选项并按新问题匹配处理

**提问语句匹配到多个标准问题**

- 产生情况：如果提问语句与所有标准问题的向量距离均未能超过match_distance设置的值，但有多个问题的向量距离在multiple_distance和match_distance之间，则框架会自动组合这些问题为选项提示客户选择他实际想问的问题
- 处理流程： 收到问题 -> 匹配到多个标准问题 -> 将问题清单组合为选项答案文本回复 ->  客户回答选项序号 -> 根据上下文找到选项序号对应的选项标准问题ID，执行该标准问题的回答处理
- 跳出条件：与上一种情况一样

注意：客户选择选项后找到标准问题答案，是**执行回答处理**，而**不是返回答案文本**。如果对应的标准问题答案类型是options，则可以产生多级选项的问答效果；如果答案类型是ask或job，则能执行其他方式的对话场景。

## job（执行任务）

job模式的答案将会通过对话插件模式执行自定义的插件函数，例如查找一个随机标准问题答案进行回答。

- 设置方法：标准问题答案的a_type字段设置为job，type_param字段设置为插件参数，格式为 “**['插件类名', '插件函数名', {插件的调用扩展入参字典}]**”，例如：“['InitJob', 'get_random_answer', {'ids': [{1, 2, 3]}]” 会调用job类型插件中的InitJob.get_random_answer(..., **{'ids': [{1, 2, 3]}) ，从1，2，3这3个标准问题中随机找一个进行回答处理
- 处理流程：收到问题 -> 匹配到任务问题 -> 从插件列表中找到所配置的插件函数执行 -> 根据插件执行结果处理（直接回复问题答案文本，或跳转到另外一个标准问题进行回答处理）

## ask（提问模式）

提问模式是由系统向客户提出问题，并根据客户的回答进行进一步的处理，例如询问客户地址等。

- 设置方法：标准问题答案的a_type字段设置为ask，type_param字段设置为插件参数，格式为 **“['插件类名', '插件函数名', '问题分类', '问题场景', {插件的调用扩展入参字典}, 第一次是否直接执行]**”， 例如："['TestAskPlugins', 'test_pay_fun', 'test_finance', '', {}, True, ]"  将调用“ask” 类型插件的TestAskPlugins.test_pay_fun
- 处理流程：收到问题 -> 匹配到提问模式问题 -> 将问题信息添加到上下文 -> 向客户提问 -> 客户回答问题 -> 根据上下文执行问题对应的插件函数 -> 根据插件执行结果处理（直接回复问题答案文本-跳出提问，或跳转到另外一个标准问题进行回答处理，或者重新发起提问）

注意：

- 如果指定了第一次直接执行（设置为True），则再第一次匹配到问题后直接先执行插件函数，再根据插件函数的返回值回答客户；
- 连续的多次提问有相同的上下文id进行数据关联，但一旦跳出了提问则上下文将被清除。



# NLP对话意图识别

可以通过设置  server.xml 配置中的 use_nlp 参数打开NPL对话意图识别的功能，该功能会根据客户提问语句的关键词匹配客户的实际意图，进而执行该意图对应的标准问题答案，例如客户提问 “我要给XX转账100元” ，可以通过关键词 “转账” 匹配到 **转账** 意图，从而执行转账的答案处理。（目前只支持关键词匹配，未来计划增加正则表达式规则，支持更多形式的匹配规则）

- 设置方法：设置意图配置字典（NlpPurposConfigDict）的信息，主要包括：
  
  - order_num 定义了意图搜索优先级，数字越大优先级越高，如果匹配到多个意图，将只返回优先级最高的意图
  
  - std_question_id 为匹配意图后执行的标准问题ID；
  
  - collection，partition 指定意图对应的问题分类和场景

  - match_collection，match_partition 指定要在哪个问题分类和场景下匹配意图，可用这两个值对意图进行分类
  
  - exact_match_words 为精确匹配意图的关键字清单，将会按整个问题进行匹配，格式为 “**['关键词', '关键词', ... ]**” ，例如设置 “ ['下一个', '继续', 'more'] ” 来匹配 **下一步操作** 意图
  
  - exact_ignorecase 可以设置精确匹配意图关键字是否忽略大小写，默认为 'N'
  
  - match_words 为分词匹配关键词清单，按照问题语句分词后匹配是否在意图词组中，格式为 “**['关键词', '关键词', ... ]**” ，例如设置 “ ['转账', '转钱', '打钱'] ” 来匹配 **转账** 意图
  
  - ignorecase 可以设置分词匹配是否忽略大小写，默认为 'N'
  
  - word_scale 可以设置分词匹配词比例控制，例如可以设置 word_scale 为 0.5，则问题语句 “你好啊” 中匹配上的 “你好” 占整个问题比例超过 0.5 , 视为匹配上；而 “朋友你好啊” 中匹配上的 “你好” 占整个问题比例低于 0.5 ， 视为未匹配上
  
  - check 设置为检查意图插件的参数配置，格式为 "**['插件类名', '插件函数名', {插件的调用扩展入参字典}]**"，例如 "['InitCheck', 'reject_by_nest', {'next': {'天气': ['真好', '不错', '真差']}, }]" 将调用 “nlpcheck” 类型插件InitCheck.reject_by_nest(... , **{扩展入参}) ， 并根据函数返回的True和Fasle确认是否真正匹配了意图
  
  - info 设置为获取意图辅助信息，如果意图对应的问答模式是job或ask，获取到的辅助信息将会传入对应标准问题所调用插件的扩展入参字典；配置格式为 “**['插件类名', '插件函数名', {插件的调用扩展入参字典}]**”，例如 “['InitInfo', 'get_by_words', {'condition': [{'key': 'amount', 'class': ['m']}, {'key': 'in_name', 'class': ['nr']}]}]” 将调用 “nlpinfo” 类型插件的InitInfo.get_by_words获取问题中的信息，以字典方式返回，返回的字典将送入标准问题对应的插件调用的扩展入参中
  
    
  
- 处理流程：收到问题 -> 进行NLP意图匹配 -> (如果匹配上)执行意图对应问题的回答处理（可能是text、options、job、ask）的任意一种



# 预定义替换符

回复出去的答案可以通过预定义替换符替换中间的内容，让答案文本在反馈的时候根据上下文进行调整，需要支持预定义替换符，需要将答案信息（Answers）的 replace_pre_def 字段设置为Y，并在答案的文本内容中使用 {$xx=xx$} 格式进行定义，目前支持的替换符包括：

- {$info=key$} ：从session中获取info字典的key对象值进行替换
- {$cache=key$} : 从session的cache缓存（与上下文相关）字典的key对象值进行替换
- {$config=key$} : 从 server.xml 的 qa_config 字典的key对象值进行替换
- {$para=key$} : 从 CommonPara 表获取制定para的值进行替换



# 对话插件扩展

待补充

