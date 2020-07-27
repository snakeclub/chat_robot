// 自定义函数
(function ($) {
    // 登记最后一次显示的时间
    $.LastShowTime = new Date();

    // 间隔多少秒要重新显示日期
    $.ShowTimeBetween = 300;

    // 是否开启Token验证
    $.UseToken = false;

    // API接口调用信息
    $.UserId = "";
    $.Token = "";

    // 客户的sessionID
    $.SessionId = "";
    $.user_id = 1;
    $.user_name = '黎慧剑';


    // 检查是否要增加时间
    $.CheckAddTimeStamp = function () {
        var now = new Date();
        var time = timeBetween($.LastShowTime, now, "s");
        if (time > $.ShowTimeBetween) {
            // 超过间隔时间，添加时间显示
            $.AddTimeStamp();
        };

        // 有检查代表有新的显示，更新最后时间
        $.LastShowTime = new Date();
    };

    // 聊天记录中增加当前时间
    $.AddTimeStamp = function () {
        var formatStr = "yyyy年M月d日 周W hh:mm:ss";
        $.LastShowTime = new Date();
        var html = "<p style=\"text-align: center;\">" + $.LastShowTime.Format(formatStr) + "</p>";

        // 添加到聊天记录结尾
        $("#chat_logs").append(html);
    };

    // 显示思考中提示
    $.ShowThinkingTips = function () {
        $("#thinking").show();
        // 添加查询中
        var html = "<div id=\"search_tips\" style=\"text-align: center; margin-top: 10px;\">正在查询相关问题,请稍后...</div>";
        $("#chat_logs").append(html)
    };

    // 隐藏思考中提示
    $.HideThinkingTips = function () {
        $("#thinking").hide();
        // 删除查询中对象
        $("#search_tips").remove();
    };

    // 聊天记录中增加问题
    $.AddQuestion = function (question) {
        // 检查是不是要显示时间
        $.CheckAddTimeStamp();

        var html = "<div class=\"jss109 question\" style=\"flex-direction: row-reverse;\"> \
            <div class=\"jss111\" style=\"margin: 0px 20px 0px 0px;\"> \
                <p>" + question + "</p> \
            </div></div>";
        // 添加到聊天记录结尾
        $("#chat_logs").append(html);
        $("#chat_logs").scrollTop($("#chat_logs").get(0).scrollHeight);
    };

    // 聊天记录中增加答案
    $.AddAnswer = function (answer) {
        // 检查是不是要显示时间
        $.CheckAddTimeStamp();

        var html = "<div class=\"jss109 answer\"> \
            <div class=\"jss110\"></div> \
                <div class=\"jss111\"> \
                    <div class=\"jss113\" style=\"left: -10px;\"></div> \
                        <p>" + answer + "</p> \
            </div></div>";
        // 添加到聊天记录结尾
        $("#chat_logs").append(html);
        $("#chat_logs").scrollTop($("#chat_logs").get(0).scrollHeight);
    };

    // 进行问题查询
    $.QuestionSearch = function () {
        // 获取问题框问题
        var question = $("#input_question").val();
        if (question == "") {
            return;
        };

        // 问题框置空
        $("#input_question").val("");

        // 先添加到问题记录中
        $.HideThinkingTips();
        $.AddQuestion(question);

        // 显示思考中再发起远程查询
        $.ShowThinkingTips();

        // 到服务器端搜查答案
        $.AddTimer(
            'SearchAnswer',
            function () {
                $.AjaxSearchAnswer(question);
            },
            1
        );
    };

    // 处理知识内容展示
    $.AddKnowledgeContent = function (answers) {
        contents = answers.contents;
        title = answers.title

        // 先组织标题
        var html = "<table class=\"KnowledgeTable\">";
        if (title && title != "") { // 有标题的情况
            html += "<tr><td><a class=\"KnowledgeTitle\">" + title + "</a></td></tr>";
        }

        // 遍历内容
        for (var i = 0; i < contents.length; i++) {
            content = contents[i];
            html += '<tr><td>';

            // 处理图片
            if (content.images != null) {
                html += "<div class=\"KnowledgeImgContainer KnowledgeImgContainer";
                if (content.images.para == 'right') {
                    html += "Right\">";
                } else {
                    html += "Left\">";
                }
                html += "<a href=\"" + content.images.url + "\" target=\"_blank\"><img src=\"" + content.images.thumbnail + "\" alt=\"" + content.images.notes + "\" /></a>";
                html += "<br /><a>" + content.images.notes + "</a></div>"
            }

            // 处理内容
            html += "<p>" + content.content + "</p></td></tr>";
        };

        // 处理操作菜单
        html += '<tr><td>';
        // 上一个章节
        html += '<a href="#" onclick="$.AjaxKnowledgeAction(\'prev\', ' + answers.current_id + ');">上一个</a><a>&nbsp;&nbsp;|&nbsp;&nbsp;</a>';
        if (answers.more) {
            html += '<a href="#" onclick="$.AjaxKnowledgeAction(\'more\', ' + answers.current_id + ');">查看更多</a><a>&nbsp;&nbsp;|&nbsp;&nbsp;</a>';
        }
        html += '<a href="#" onclick="$.AjaxKnowledgeAction(\'next\', ' + answers.current_id + ');">下一个</a>';
        html += '</td></tr>';

        // 处理内容
        html += "</table>";

        // 添加到答案中
        $.AddAnswer(html);
    };

    // 处理投诉内容展示
    $.ShowComplaintForm = function (is_summit, user_name, message, form_info) {
        // 初始化参数
        if (!user_name) {
            user_name = $.user_name;
        }
        if (!message) {
            message = "";
        }

        // 添加值
        if (is_summit) {
            // 需要提交
            $("#complaint_user_name").val(user_name);
            $("#complaint_text").val(message);
        } else {
            // 显示详情
            $("#complaint_user_name").val(form_info.data.user_name);
            $("#complaint_text").val(form_info.data.content);
            $("#complaint_time").text(form_info.create_time);
            $("#complaint_status").text(form_info.status);
            if (form_info.data.response) {
                $("#return_complaint").html("<span>" + JSON.stringify(form_info.data.response) + "</span>");
            } else {
                $("#return_complaint").html("");
            }

        }


        // 显示及隐藏
        if (is_summit) {
            //需要提交
            $("#complaint_tips").show();
            $("#complaint_send").show();
            $("#complaint_time").hide();
            $("#complaint_status").hide();
            $("#return_complaint").hide();
        } else {
            // 显示详情
            $("#complaint_tips").hide();
            $("#complaint_send").hide();
            $("#complaint_time").show();
            $("#complaint_status").show();
            $("#return_complaint").show();
        }

        // 显示投诉框
        $('#complaint').show();
    };

    // 统一的响应消息处理函数
    $.LastComplaintFormId = -1;
    $.LastLeaveMessageId = -1;
    $.CommonAnswerShow = function (is_resp, msg_type, msg, create_time) {
        if (msg_type == 'text') {
            // 文本展示和处理
            $.AddAnswer(msg.join("<br />"));
            return
        }

        // json对象的处理
        if (msg.data_type == 'knowledge_content') {
            // 知识内容处理
            $.AddKnowledgeContent(msg);
        } else if (msg.data_type == 'form') {
            // 表单的处理
            if (msg.form_type == "complaint") {
                // 投诉表单
                if (msg.action == 'create') {
                    // 创建新投诉
                    $.ShowComplaintForm(true, msg.default.user_name, msg.default.content);
                } else if (msg.action == 'preview') {
                    // 投诉预览
                    var html = "<table class=\"KnowledgeTable\">";
                    html += "<tr><td><a class=\"KnowledgeTitle\">" + "投诉" + "</a></td></tr>";
                    html += "<tr><td>" + msg.status + "</td></tr>";
                    html += "<tr><td>" + msg.preview.content + "</td></tr>";
                    html += '<tr><td><a href="#" onclick="$.AjaxGetComplaintFormDetail(' + msg.form_id + ')">详情</a></td></tr></table>';
                    if (is_resp) {
                        // 请求响应，添加到问题显示
                        $.AddQuestion(html);
                        $.LastComplaintFormId = msg.form_id;
                    } else {
                        // 主动推送，添加到答案显示
                        $.AddAnswer(html);
                    }
                } else if (msg.action == 'detail') {
                    // 投诉详情, 打开投诉窗口并显示
                    $.ShowComplaintForm(false, '', '', msg);
                }
            } else {
                $.AddAnswer("不支持的表单类型: " + JSON.stringify(msg));
                return;
            }
        } else if (msg.data_type == 'options') {
            // 选项显示处理
            var show_text = msg.tips + "<br />";
            for (var i = 0; i < msg.options.length; i++) {
                show_text += '<a href="#" onclick="$.AjaxSearchAnswer(\'' + msg.options[i].index + '\', null, ' + msg.options[i].std_question_id + ');">' + msg.options[i].option_str + '</a><br />';
            }
            $.AddAnswer(show_text);
            return;
        } else if (msg.data_type == 'leave_message') {
            // 留言消息处理
            if (msg.action == 'add') {
                // 新增留言的提示
                var html = "<table class=\"KnowledgeTable\">";
                html += "<tr><td>" + msg.tips + "</td></tr>";
                html += '<tr id="leave_message_' + msg.context_id + '"><td><a href="#" onclick="$.AjaxLeaveMessageSelectFile(\'' + msg.context_id + '\');">上传图片</a><a>&nbsp;&nbsp;|&nbsp;&nbsp;</a>';
                html += '<a href="#" onclick="$.AjaxLeaveMessageCancle(\'' + msg.context_id + '\');">取消留言</a></td></tr></table>';
                html += '<input type="file" id="leave_message_file_' + msg.context_id + '" multiple onchange="$.AjaxLeaveMessageUpload(\'' + msg.context_id + '\');" style="display:none;" />';
                $.AddAnswer(html);
            } else if (msg.action == 'success' || msg.action == 'cancle') {
                // 成功或取消，屏蔽按钮功能
                $("#leave_message_" + msg.context_id).hide();
                $.AddAnswer(msg.tips);
                if (msg.action == 'success') {
                    $.LastLeaveMessageId = msg.msg_id;
                }
            } else if (msg.action == 'resp') {
                // 回复
                var html = "<table class=\"KnowledgeTable\">";
                html += "<tr><td>回复: " + msg.msg + "</td></tr>";
                html += "<tr><td>" + msg.tips + "</td></tr>";
                for (var i = 0; i < msg.resp_pic_urls.length; i++) {
                    if (msg.resp_pic_urls[i].length > 0) {
                        html += "<tr><td><a href=\"" + msg.resp_pic_urls[i] + "\" target=\"_blank\">附件" + i + "</a></td></tr>";
                    }
                }
                html += "<tr><td><a href=\"#\" onclick=\"$.AjaxLeaveMessageRefAdd(" + msg.msg_id + ");\">追加留言</a></td></tr></table>";
                $.AddAnswer(html);
            }
            return;
        } else {
            // 不支持的数据类型
            $.AddAnswer("不支持的数据类型: " + JSON.stringify(msg));
            return;
        }
    };

    //执行登陆动作
    $.AjaxLogin = function (user_name, password) {
        // 生成调用参数
        var sendObj = new Object();
        sendObj.user_name = user_name;
        sendObj.password = password;

        $.ajax({
            url: "/api/Client/login",
            type: 'post',
            contentType: 'application/json',
            data: JSON.stringify(sendObj),
            timeout: 5000,
            async: false, // 设置同步完成
            success: function (retObj) {
                if (retObj.status == '00000') {
                    $.UserId = retObj.user_id;
                    $.user_name = user_name;
                    $.Token = retObj.token;
                } else {
                    alert("用户登陆失败[" + retObj.status + "]: " + retObj.msg);
                };
            },
            error: function (xhr, status, error) {
                alert("用户登陆异常: " + error);
            },
        });
    };

    $.AjaxGenerateToken = function () {
        $.ajax({
            url: "/api/Qa/GenerateToken",
            type: 'get',
            // contentType: 'application/json',
            headers: {
                UserId: $.UserId,
                Authorization: 'JWT ' + $.Token
            },
            data: null,
            timeout: 5000,
            async: false, // 设置同步完成
            success: function (retObj) {
                if (retObj.status == '00000') {
                    $.Token = retObj.token;
                } else {
                    alert("更新token失败[" + retObj.status + "]: " + retObj.msg);
                };
            },
            error: function (xhr, status, error) {
                alert("更新token失败: " + error);
            },
        });
    };

    // 获取Session ID
    $.AjaxGetSessionId = function () {
        // 生成调用参数
        var sendObj = new Object();
        sendObj.user_id = $.user_id;
        sendObj.user_name = $.user_name;

        var headers = {};
        if ($.UseToken) {
            headers = {
                UserId: $.UserId,
                Authorization: 'JWT ' + $.Token
            };
        }

        $.ajax({
            url: "/api/Qa/GetSessionId",
            type: 'post',
            contentType: 'application/json',
            headers: headers,
            data: JSON.stringify(sendObj),
            timeout: 5000,
            async: false, // 设置同步完成
            success: function (retObj) {
                if (retObj.status == '00000') {
                    $.SessionId = retObj.session_id;
                } else {
                    alert("获取Session ID失败[" + retObj.status + "]: " + retObj.msg);
                };
            },
            error: function (xhr, status, error) {
                alert("获取Session ID异常: " + error);
            },
        });
    };

    /*
    $.SearchAnswer(question, classify)
        获取问题答案

        @param {str} question - 提出的问题
        @param {array} classify=null - 指定要搜索的主题，例如'food'
    */
    $.AjaxSearchAnswer = function (question, collection, std_question_id, std_question_tag) {
        // 入参默认值
        if (!collection) {
            collection = null;
        };
        if (!std_question_id) {
            std_question_id = null;
        };
        if (!std_question_tag) {
            std_question_tag = null;
        };

        // 生成调用参数
        var sendObj = new Object();
        sendObj.session_id = $.SessionId;
        sendObj.question = question;
        sendObj.collection = collection;
        sendObj.std_question_id = std_question_id;
        sendObj.std_question_tag = std_question_tag;

        var headers = {};
        if ($.UseToken) {
            headers = {
                UserId: $.UserId,
                Authorization: 'JWT ' + $.Token
            };
        }

        // 调用问题查询处理
        var retObj = null;
        $.ajax({
            url: "/api/Qa/SearchAnswer",
            type: 'post',
            contentType: 'application/json',
            headers: headers,
            data: JSON.stringify(sendObj),
            timeout: 5000,
            async: false, // 设置同步完成
            success: function (result) {
                retObj = result;
            },
            error: function (xhr, status, error) {
                alert("获取问题答案异常: " + error);
            },
        });

        // 处理显示
        if (retObj != null) {
            if (retObj.status.substr(0, 1) != "0") {
                // 出现失败
                if (retObj.status == '10002') {
                    // session id不存在，重新获取session ID，并重新执行
                    $.AjaxGetSessionId();
                    $.AjaxSearchAnswer(question, collection, std_question_id, std_question_tag);
                    return;
                }

                alert("获取问题答案失败[" + retObj.status + "]: " + retObj.msg);
            }

            $.CommonAnswerShow(true, retObj.answer_type, retObj.answers);
        };

        // 隐藏思考中
        $.HideThinkingTips();
    };

    /*
    $.AjaxKnowledgeAction(action, chapter_id)
        直接获取指定知识章节的关联章节信息
        @param {str} action - 操作, prev/next/more
        @param {int} chapter_id - 当前章节id
    */
    $.AjaxKnowledgeAction = function (action, chapter_id) {
        var question = "{'action': '" + action + "', 'chapter_id': " + chapter_id + "}";
        $.AjaxSearchAnswer(question, 'knowledge', null, 'knowledge_direct_action');
    };

    /*
    根据表单id获取投诉详细信息
    */
    $.AjaxGetComplaintFormDetail = function (form_id) {
        var question = "{'form_type': 'complaint', 'action': 'get', 'form_id': " + form_id + "}";
        $.AjaxSearchAnswer(question, 'chat', null, 'form_direct_action');
    };

    // 提交投诉消息
    $.AjaxSaveComplaintForm = function () {
        var question = "{'form_type': 'complaint', 'action': 'save', 'user_id': ";
        question += $.user_id + ", 'user_name': '" + $.user_name + "', 'data': {'user_name': '" + $("#complaint_user_name").val() + "', 'content': '" + $("#complaint_text").val() + "'}}";
        $.AjaxSearchAnswer(question, 'chat', null, 'form_direct_action');
        $('#complaint').hide();
    };

    // 新增最后投诉问题的回答
    $.AjaxAddComplaintRespMsg = function () {
        if ($.LastComplaintFormId == -1) {
            alert('需要先提交一个投诉表单!');
            return;
        }

        // 生成调用参数
        var sendObj = new Object();
        sendObj.user_name = 'test';
        sendObj.password = '123456';
        sendObj.form_id = $.LastComplaintFormId;
        sendObj.resp_msg = '测试回复消息';
        sendObj.upd_status = 'treated';

        $.ajax({
            url: "/api/ComplaintFormServer/RespMsg",
            type: 'post',
            contentType: 'application/json',
            data: JSON.stringify(sendObj),
            timeout: 5000,
            async: false, // 设置同步完成
            success: function (retObj) {
                if (retObj.status == '00000') {
                    ;
                } else {
                    alert("回复投诉失败[" + retObj.status + "]: " + retObj.msg);
                };
            },
            error: function (xhr, status, error) {
                alert("回复投诉异常: " + error);
            },
        });

    };

    // 上传文件
    $.UploadPicIndex = 0; // 用来记录上传文件的索引序号，用于找回图片的地址进行替换

    // 获取上传文件的本地路径
    $.GetUploadFileLocalPath = function (file) {
        var url = null;
        if (window.createObjectURL != undefined) { // basic
            url = window.createObjectURL(file);
        } else if (window.URL != undefined) { // mozilla(firefox)
            url = window.URL.createObjectURL(file);
        } else if (window.webkitURL != undefined) { // webkit or chrome
            url = window.webkitURL.createObjectURL(file);
        }
        return url;
    };

    $.AjaxUploadFile = function (upload_type, note) {
        // 获取file标签选择器的文件
        var files = $('#file').get(0).files;

        // 遍历多个文件上传
        for (var i = 0; i < files.length; i++) {
            // 文件信息
            var file_obj = files[i];
            $.UploadPicIndex = $.UploadPicIndex + 1;
            var file_id = "upload_pic_" + $.UploadPicIndex;
            var file_local_path = $.GetUploadFileLocalPath(file_obj);

            // 将文件对象打包成form表单类型的数据
            var formdata = new FormData;
            formdata.append('file', file_obj);

            var headers = {};
            if ($.UseToken) {
                headers = {
                    UserId: $.UserId,
                    Authorization: 'JWT ' + $.Token
                };
            }

            // 进行文件数据的上传
            $.ajax({
                url: '/api/Qa/UploadFile/' + upload_type + '/' + note + '/' + file_id,
                type: 'post',
                contentType: false,
                headers: headers,
                data: formdata,
                processData: false,
                async: true, // 异步处理
                success: function (result) {
                    // 对数据json解析
                    var retObj = result;
                    if (retObj.status == "00000") {
                        // 上传成功
                        $("#" + retObj.interface_seq_id).attr("src", retObj.answers.thumbnail);
                        $("#a_" + retObj.interface_seq_id).attr("href", retObj.url);
                    } else {
                        // 上传失败
                        $("#" + retObj.interface_seq_id).attr("src", "/static/pic/error.jpg");
                    }
                }
            });

            // 添加上传指示图片显示
            var pic_html = "<div class=\"ShowPic\">\
                <a id=\"a_" + file_id + "\" href=\"/static/pic/uploading.gif\" target=\"_blank\">\
                <img id=\"" + file_id + "\"  src=\"/static/pic/uploading.gif\" local_path=\"" + file_local_path + "\">\
            </a></div>";

            $.AddQuestion(pic_html)

        }

    };


    // 取消留言
    $.AjaxLeaveMessageCancle = function (context_id) {
        var question = "{'action': 'cancle', 'context_id': '" + context_id + "'}";
        $.AjaxSearchAnswer(question, 'chat', null, 'leave_message_direct_action');
    };

    // 选择上传留言图片
    $.AjaxLeaveMessageSelectFile = function (context_id) {
        // 清空前面的文件选择
        var obj = document.getElementById('leave_message_file_' + context_id);
        if (obj.outerHTML) {
            obj.outerHTML = obj.outerHTML;
        } else {
            obj.value = "";
        }

        // 打开文件上传选择框
        $("#leave_message_file_" + context_id).click();
    };

    // 上传留言图片
    $.AjaxLeaveMessageUpload = function (context_id) {
        // 上传文件
        var files = $("#leave_message_file_" + context_id).get(0).files;

        // 遍历多个文件上传
        for (var i = 0; i < files.length; i++) {
            // 文件信息
            var file_obj = files[i];

            // 将文件对象打包成form表单类型的数据
            var formdata = new FormData;
            formdata.append('file', file_obj);

            var headers = {};
            if ($.UseToken) {
                headers = {
                    UserId: $.UserId,
                    Authorization: 'JWT ' + $.Token
                };
            }

            // 进行文件数据的上传
            $.ajax({
                url: '/api/Qa/UploadFile/' + 'leave_message_file' + '/' + 'pic' + '/' + context_id,
                type: 'post',
                contentType: false,
                headers: headers,
                data: formdata,
                processData: false,
                async: true, // 异步处理
                success: function (result) {
                    // 对数据json解析
                    var retObj = result;
                    if (retObj.status == "00000") {
                        // 上传成功
                        var question = "{'action': 'upload_file', 'context_id': '" + context_id + "', 'url': '" + retObj.url + "'}";
                        $.AjaxSearchAnswer(question, 'chat', null, 'leave_message_direct_action');
                    } else {
                        // 上传失败
                        $.AddAnswer('图片上传失败[' + retObj.status + '][' + retObj.msg + ']:' + JSON.stringify(file_obj))
                    }
                }
            });
        };
    };

    // 追加留言
    $.AjaxLeaveMessageRefAdd = function (msg_id) {
        var question = "{'ref_id': " + msg_id + "}";
        $.AjaxSearchAnswer(question, 'chat', null, 'leave_message_direct_action');
    };

    // 添加留言回复信息
    $.AjaxAddLeaveMessageRespMsg = function () {
        if ($.LastLeaveMessageId == -1) {
            alert('需要先提交一个留言!');
            return;
        }

        // 生成调用参数
        var sendObj = new Object();
        sendObj.user_name = 'test';
        sendObj.password = '123456';
        sendObj.msg_id = $.LastLeaveMessageId;
        sendObj.resp_msg = '测试回复留言消息';
        sendObj.upd_status = 'treated';

        $.ajax({
            url: "/api/LeaveMessagePluginServer/RespMsg",
            type: 'post',
            contentType: 'application/json',
            data: JSON.stringify(sendObj),
            timeout: 5000,
            async: false, // 设置同步完成
            success: function (retObj) {
                if (retObj.status == '00000') {
                    ;
                } else {
                    alert("回复留言失败[" + retObj.status + "]: " + retObj.msg);
                };
            },
            error: function (xhr, status, error) {
                alert("回复留言异常: " + error);
            },
        });
    };


    // 添加测试服务端消息
    $.AjaxAddSendMessage = function () {
        var sendObj = new Object();
        sendObj.user_id = $.user_id;
        sendObj.from_user_name = '测试';
        sendObj.msg = '测试服务端消息';

        var headers = {};
        if ($.UseToken) {
            headers = {
                UserId: $.UserId,
                Authorization: 'JWT ' + $.Token
            };
        }

        var retObj = null;
        $.ajax({
            url: "/api/Client/AddSendMessage",
            type: 'post',
            contentType: 'application/json',
            headers: headers,
            data: JSON.stringify(sendObj),
            timeout: 5000,
            async: false, // 设置同步完成
            success: function (result) {
                retObj = result;
            },
            error: function (xhr, status, error) {
                alert("新增服务端消息异常: " + error);
            },
        });
    };


    // 获取服务端消息
    $.AjaxGetMessage = function () {
        // 先检查是否有消息
        var retObj = null;
        var sendObj = new Object();
        sendObj.user_id = $.user_id;

        var headers = {};
        if ($.UseToken) {
            headers = {
                UserId: $.UserId,
                Authorization: 'JWT ' + $.Token
            };
        }

        $.ajax({
            url: "/api/Qa/GetMessageCount",
            type: 'post',
            headers: headers,
            contentType: 'application/json',
            data: JSON.stringify(sendObj),
            timeout: 5000,
            async: false, // 设置同步完成
            success: function (result) {
                retObj = result;
            },
            error: function (xhr, status, error) {
                alert("获取待收消息数量失败: " + error);
                return;
            },
        });

        if (retObj == null) {
            return;
        };

        if (retObj.status != '00000') {
            alert("获取消息数量失败[" + retObj.status + "]: " + retObj.msg);
            return;
        };

        if (retObj.message_count == 0) {
            return;
        }

        // 获取消息清单
        retObj = null;
        $.ajax({
            url: "/api/Qa/GetMessageList",
            type: 'post',
            headers: headers,
            contentType: 'application/json',
            data: JSON.stringify(sendObj),
            timeout: 5000,
            async: false, // 设置同步完成
            success: function (result) {
                retObj = result;
            },
            error: function (xhr, status, error) {
                alert("获取待收消息清单失败: " + error);
                return;
            },
        });

        if (retObj == null) {
            return;
        };

        if (retObj.status != '00000') {
            alert("获取消息清单失败[" + retObj.status + "]: " + retObj.msg);
            return;
        };

        var confirm_ids = new Array();
        for (var i = 0; i < retObj.messages.length; i++) {
            var msg = retObj.messages[i]
            $.CommonAnswerShow(false, msg.msg_type, msg.msg, msg.create_time);
            confirm_ids.push(msg.id);
        }

        // 确认已收到消息
        if (confirm_ids.length > 0) {
            var sendObj = new Object();
            sendObj.message_ids = confirm_ids;
            sendObj.user_id = $.user_id;

            retObj = null;
            $.ajax({
                url: "/api/Qa/ConfirmMessageList",
                type: 'post',
                contentType: 'application/json',
                headers: headers,
                data: JSON.stringify(sendObj),
                timeout: 5000,
                async: false, // 设置同步完成
                success: function (result) {
                    retObj = result;
                },
                error: function (xhr, status, error) {
                    alert("确认已收消息异常: " + error);
                },
            });

            if (retObj != null && retObj.status != '00000') {
                alert("确认已收消息失败[" + retObj.status + "]: " + retObj.msg);
            };

        };
    };


})(jQuery);