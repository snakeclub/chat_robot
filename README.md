# chat_robot说明
chat robot 是一个机器人对话框架，可以实现闲聊、客服问答、知识库检索等基于对话的场景应用，其基本原理是基于**BERT模型（Bidirectional Encoder Representation from Transformers）**对标准问题生成语义相似度向量并存入到**Milvus**服务中，利用**Milvus**服务快速实现客户输入问题的相似度向量的检索匹配，并返回对应的答案；此外也通过开源项目**Jieba**的NLP分词功能对语句进行分词和意图动作匹配，实现部分特殊动作的识别处理。

chat robot框架可以支持进行job、ask、options等对话插件的开发和导入，便于扩展实现各种特殊场景的对话处理。



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



### 使用MySQL5.7作为Milvus数据管理(生产环境建议)

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



## 安装chat robot

注意：chat robot需要使用mysql作为数据库服务器，请在启动前安装好MySQL并建好对应的数据库（可以与Milvus共用数据库实例，通过不同数据库区分即可）

1、将chat robot源码下载到服务器：https://github.com/snakeclub/chat_robot

2、安装依赖包，基于源码目录下的requriment.txt安装清单：

```
$ pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requriment.txt
```

3、按实际环境情况，修改 chat_robot/chat_robot/conf/server.xml的配置信息

4、使用chat_robot/chat_robot/import.py导入问答库信息，问答库的导入模板可参考chat_robot/test/questions.xlsx

```
$ python import.py import=../test/questions.xlsx truncate=true
```

注：truncate标志指定清空此前的问答库。

5、使用chat_robot/chat_robot/server.py启动问答服务

```
$ python server.py
```

程序将自动找到当前目录下的./conf/server.xml配置文件，如果需要指定其他配置文件，可以在命令中指定配置文件：

```
$ python server.py config="d:/tes/server.xml"
```







