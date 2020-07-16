// 自定义函数
(function($) {
    // 登记最后一次显示的时间
    $.LastShowTime = new Date();

    // 间隔多少秒要重新显示日期
    $.ShowTimeBetween = 300;

    // 用户信息
    $.UserId = "";
    $.UserName = "";
    $.Token = "";

    // 客户的sessionID
    $.SessionId = "";

    // 检查是否要增加时间
    $.CheckAddTimeStamp = function() {
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
    $.AddTimeStamp = function() {
        var formatStr = "yyyy年M月d日 周W hh:mm:ss";
        $.LastShowTime = new Date();
        var html = "<p style=\"text-align: center;\">" + $.LastShowTime.Format(formatStr) + "</p>";

        // 添加到聊天记录结尾
        $("#chat_logs").append(html);
    };

    // 显示思考中提示
    $.ShowThinkingTips = function() {
        $("#thinking").show();
        // 添加查询中
        var html = "<div id=\"search_tips\" style=\"text-align: center; margin-top: 10px;\">正在查询相关问题,请稍后...</div>";
        $("#chat_logs").append(html)
    };

    // 隐藏思考中提示
    $.HideThinkingTips = function() {
        $("#thinking").hide();
        // 删除查询中对象
        $("#search_tips").remove();
    };

    // 聊天记录中增加问题
    $.AddQuestion = function(question) {
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
    $.AddAnswer = function(answer) {
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
    $.QuestionSearch = function() {
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
            function() {
                $.AjaxSearchAnswer(question);
            },
            1
        );
    };

    // 处理知识内容展示
    $.AddKnowledgeContent = function(content, title) {
        // 先组织内容
        var html = "<table class=\"KnowledgeTable\"><tr><td>";
        if (title && title != "") { // 有标题的情况
            html += "<a class=\"KnowledgeTitle\">" + title + "</a></td></tr><tr><td>";
        }
        // 处理图片
        if (content.images != null) {
            html += "<div class=\"KnowledgeImgContainer KnowledgeImgContainer";
            if (content.images.para == 'rigth') {
                html += "Right\">";
            } else {
                html += "Left\">";
            }
            html += "<img src=\"" + content.images.url + "\" alt=\"" + content.images.notes + "\" />";
            html += "<br /><a>" + content.images.notes + "</a></div>"
        }
        // 处理内容
        html += "<p>" + content.content + "</p></td></tr></table>";

        // 添加到答案中
        $.AddAnswer(html);
    };

    //执行登陆动作
    $.AjaxLogin = function(username, password) {
        // 生成调用参数
        var sendObj = new Object();
        sendObj.username = username;
        sendObj.password = password;

        $.ajax({
            url: "/api/Client/login",
            type: 'post',
            contentType: 'application/json',
            data: JSON.stringify(sendObj),
            timeout: 5000,
            async: false, // 设置同步完成
            success: function(retObj) {
                if (retObj.status == '00000') {
                    $.UserId = retObj.user_id;
                    $.UserName = username;
                    $.Token = retObj.token;
                } else {
                    alert("用户登陆失败[" + retObj.status + "]: " + retObj.msg);
                };
            },
            error: function(xhr, status, error) {
                alert("用户登陆异常: " + error);
            },
        });
    };

    $.AjaxGenerateToken = function() {
        $.ajax({
            url: "/api/Qa/GenerateToken",
            type: 'get',
            contentType: 'application/json',
            headers: {
                UserId: $.UserId,
                Authorization: 'JWT ' + $.Token
            },
            data: null,
            timeout: 5000,
            async: false, // 设置同步完成
            success: function(retObj) {
                if (retObj.status == '00000') {
                    $.Token = retObj.token;
                } else {
                    alert("更新token失败[" + retObj.status + "]: " + retObj.msg);
                };
            },
            error: function(xhr, status, error) {
                alert("更新token失败: " + error);
            },
        });
    };

    // 获取Session ID
    $.AjaxGetSessionId = function() {
        // 生成调用参数
        var sendObj = new Object();
        sendObj.user_id = 1;
        sendObj.name = '黎慧剑';

        $.ajax({
            url: "/api/Qa/GetSessionId",
            type: 'post',
            contentType: 'application/json',
            headers: {
                UserId: $.UserId,
                Authorization: 'JWT ' + $.Token
            },
            data: JSON.stringify(sendObj),
            timeout: 5000,
            async: false, // 设置同步完成
            success: function(retObj) {
                if (retObj.status == '00000') {
                    $.SessionId = retObj.session_id;
                } else {
                    alert("获取Session ID失败[" + retObj.status + "]: " + retObj.msg);
                };
            },
            error: function(xhr, status, error) {
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
    $.AjaxSearchAnswer = function(question, classify) {
        // 入参默认值
        if (!classify) {
            classify = null;
        };

        // 生成调用参数
        var sendObj = new Object();
        sendObj.session_id = $.SessionId;
        sendObj.question = question;
        sendObj.collection = classify;

        // 调用问题查询处理
        var retObj = null;
        $.ajax({
            url: "/api/Qa/SearchAnswer",
            type: 'post',
            contentType: 'application/json',
            headers: {
                UserId: $.UserId,
                Authorization: 'JWT ' + $.Token
            },
            data: JSON.stringify(sendObj),
            timeout: 5000,
            async: false, // 设置同步完成
            success: function(result) {
                retObj = result;
            },
            error: function(xhr, status, error) {
                alert("获取问题答案异常: " + error);
            },
        });

        // 处理显示
        if (retObj != null) {
            if (retObj.status.substr(0, 1) != "0") {
                // 出现失败
                alert("获取问题答案失败[" + retObj.status + "]: " + retObj.msg);
            }

            if (retObj.answer_type == 'text') {
                // 文本格式的处理
                if (retObj.status == "00000") {
                    // 只返回一个答案
                    $.AddAnswer(retObj.answers[0]);
                } else {
                    // 返回多个，组合一起
                    $.AddAnswer(retObj.answers.join("<br />"));
                }
            } else {
                // json格式的处理
                if (retObj.answers.data_type == 'knowledge_content') {
                    // 知识内容处理
                    $.AddKnowledgeContent(retObj.answers.contents[0], retObj.answers.title);

                    // 处理后续的内容
                    for (var i = 1; i < retObj.answers.contents.length; i++) {
                        $.AddKnowledgeContent(retObj.answers.contents[i]);
                    }
                } else {
                    // 不支持的数据类型
                    alert("不支持的数据类型: " + JSON.stringify(retObj));
                }

            }
        };

        // 隐藏思考中
        $.HideThinkingTips();
    };


    // 上传文件
    $.UploadPicIndex = 0; // 用来记录上传文件的索引序号，用于找回图片的地址进行替换

    // 获取上传文件的本地路径
    $.GetUploadFileLocalPath = function(file) {
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

    $.AjaxUploadFile = function(upload_type, note) {
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

            // 进行文件数据的上传
            $.ajax({
                url: '/api/Qa/UploadFile/' + upload_type + '/' + note + '/' + file_id,
                type: 'post',
                contentType: false,
                headers: {
                    UserId: $.UserId,
                    Authorization: 'JWT ' + $.Token
                },
                data: formdata,
                processData: false,
                async: true, // 异步处理
                success: function(result) {
                    // 对数据json解析
                    var retObj = result;
                    if (retObj.status == "00000") {
                        // 上传成功
                        $("#" + retObj.interface_seq_id).attr("src", retObj.url)
                            // 如果有答案，添加答案
                        if (retObj.answers.length > 0) {
                            $.AddAnswer(retObj.answers.join("<br />"));
                        }
                    } else {
                        // 上传失败
                        $("#" + retObj.interface_seq_id).attr("src", "/static/pic/error.jpg")
                    }
                }
            });

            // 添加上传指示图片显示
            var pic_html = "<div class=\"ShowPic\">\
                <img id=\"" + file_id + "\" src=\"/static/pic/uploading.gif\" local_path=\"" + file_local_path + "\">\
            </div>";

            $.AddQuestion(pic_html)

        }

    };


})(jQuery);