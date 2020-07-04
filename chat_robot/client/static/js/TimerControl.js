/*-----------------------
JQuery-UITool v1.0.0
完成时间：2011-
作者：黎慧剑
联系方式:snakeclub@163.com
程序说明：基于JQuery框架的Web界面便捷工具,基于该工具，可以通过简单的函数调用实现各类Web界面效果，简化Web开发

当前控件：TimerControl
说明：定时器控件控件
文件：TimerControl.js
依赖文件：jquery-1.6.4.min.js
-----------------------*/

/*-----------------------
==TimerControl==
说明：定时器控件控件
-----------------------*/
;(function($) {
    /*
      --JQuery_UITool_TimerControl_TimerList--
      共享变量，用于存储需要执行的Timer对象
    */
    var JQuery_UITool_TimerControl_TimerList = new Array(0);

    /*
      --TimerControl_Run--
      TimerControl_Run(TimerID)
      内部函数，真正执行定时任务的函数，用于进行后续处理(循环或其他清除定时任务)
        TimerID : 定时器ID
    */
    $.TimerControl_Run = function(TimerID){
        for(var i = 0;i<JQuery_UITool_TimerControl_TimerList.length;i++){
            if(JQuery_UITool_TimerControl_TimerList[i].timerID == TimerID){
                try{
                    //执行语句
                    try{
                       JQuery_UITool_TimerControl_TimerList[i].funJs();
                    }
                    catch(e){;}
                }catch(e){;}
                //判断是否循环处理
                if(JQuery_UITool_TimerControl_TimerList[i].isLoop){
                    //循环情况不处理
                    return;
                }
                else{
                    //不用循环，清除定时任务记录
                    JQuery_UITool_TimerControl_TimerList.splice(i,1);
                    return;
                }
            }
        }
    };
    
    /*
      --AddTimer--
      $.AddTimer(TimerID,FunJs,waitTime,[isLoop])
      建立定时器
        TimerID : 定时器ID，将来用于取消定时器用
        FunJs : 要执行的语句
        waitTime : 定时执行的时延
        [isLoop] : 是否循环运行，默认为false
    */
    $.AddTimer = function(TimerID,FunJs,waitTime){
        try{
            var tempObj = new Object();
            tempObj.timerID = TimerID;
            tempObj.waitTime = waitTime;
            tempObj.funJs = FunJs;
            if(arguments.length > 3){
                tempObj.isLoop = arguments[3];
            }
            else{
                tempObj.isLoop = false;
            }
            if(tempObj.isLoop){
                //循环执行
                tempObj.timer = setInterval(FunJs,waitTime);
            }
            else{
                //只执行一次
                tempObj.timer = setTimeout("$.TimerControl_Run('"+TimerID+"');",waitTime);
            }
            JQuery_UITool_TimerControl_TimerList.push(tempObj);
        }catch(e)
        {;}
    };
    
    /*
      --ClearTimer--
      $.ClearTimer(TimerID)
      清除选定的定时器
        TimerID : 定时器ID
    */
    $.ClearTimer = function(TimerID){
        try{
            for(var i = 0;i<JQuery_UITool_TimerControl_TimerList.length;i++){
                if(JQuery_UITool_TimerControl_TimerList[i].timerID == TimerID){
                    try{
                        if(JQuery_UITool_TimerControl_TimerList[i].isLoop){
                            clearInterval(JQuery_UITool_TimerControl_TimerList[i].timer);
                        }
                        else{
                            clearTimeout(JQuery_UITool_TimerControl_TimerList[i].timer);
                        }
                    }catch(ee){;}
                    JQuery_UITool_TimerControl_TimerList.splice(i,1);
                    return;
                }
            }
        }catch(e){;}
    };
    
    
})(jQuery);


