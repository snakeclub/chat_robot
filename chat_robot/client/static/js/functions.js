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
            url: "/api/Qa/generate_token",
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
            if (retObj.status == "00000" || retObj.status == "10000") {
                // 只返回一个答案
                $.AddAnswer(retObj.answers[0]);
            } else if (retObj.status == "00001") {
                // 返回多个，组合一起
                $.AddAnswer(retObj.answers.join("<br />"));
            } else {
                // 出现失败
                alert("获取问题答案失败[" + retObj.status + "]: " + retObj.msg);
            };
        };

        // 隐藏思考中
        $.HideThinkingTips();
    };


})(jQuery);