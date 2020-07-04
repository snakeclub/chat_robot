/*-----------------------
JQuery-UITool v1.0.0
完成时间：2011-
作者：黎慧剑
联系方式:snakeclub@163.com
程序说明：基于JQuery框架的Web界面便捷工具,基于该工具，可以通过简单的函数调用实现各类Web界面效果，简化Web开发

当前控件：PowerDate
说明：对日期的处理进行增强和优化
文件：PowerDate.js
依赖文件：
-----------------------*/
/*-----------------------
==PowerDate==
说明：增强的日期处理
-----------------------*/

/*---------------
--isLeapYear--
判断日期是否闰年
--------------- */
Date.prototype.isLeapYear = function()
{
    return (0==this.getYear()%4&&((this.getYear()%100!=0)||(this.getYear()%400==0)));
}

/*---------------
--Format--
将日期格式化为字符串格式
--------------- */
Date.prototype.Format = function(formatStr)
{
    var str = formatStr;
    var Weekn = ['7','1','2','3','4','5','6'];
    var Weekh = ['日','一','二','三','四','五','六'];
    str=str.replace(/AM/g,(this.getHours()>12?"PM":"AM"));
    str=str.replace(/yyyy/g,this.getFullYear());
    str=str.replace(/yy/g,(this.getYear() % 100)>9?(this.getYear() % 100).toString():'0' + (this.getYear() % 100));
    str=str.replace(/MM/g,this.getMonth()>8?(this.getMonth()+1).toString():'0' + (this.getMonth()+1));
    str=str.replace(/M/g,this.getMonth()+1);
    str=str.replace(/w/g,Weekn[this.getDay()]);
    str=str.replace(/W/g,Weekh[this.getDay()]);
    str=str.replace(/dd/g,this.getDate()>9?this.getDate().toString():'0' + this.getDate());
    str=str.replace(/d/g,this.getDate());
    str=str.replace(/hh/g,this.getHours()>9?this.getHours().toString():'0' + this.getHours());
    var tempH = (this.getHours()>12?(this.getHours() - 12):this.getHours());
    str=str.replace(/HH/g,tempH>9?tempH.toString():'0' + tempH);
    str=str.replace(/h/g,this.getHours());
    str=str.replace(/H/g,tempH);
    str=str.replace(/mm/g,this.getMinutes()>9?this.getMinutes().toString():'0' + this.getMinutes());
    str=str.replace(/m/g,this.getMinutes());
    str=str.replace(/ss/g,this.getSeconds()>9?this.getSeconds().toString():'0' + this.getSeconds());
    str=str.replace(/s/g,this.getSeconds());
    return str;
}

/*---------------
--stringToDate--
将指定格式的字符串转换为日期对象
--------------- */
function stringToDate(dateStr,formatStr){
    var searchStr = "yyyy|yy|MM|M|dd|d|hh|h|mm|m|ss|s";
    var dret = new Date(1900,1,1);
    var searchNext = true;  //是否继续搜索下一个
    //一些临时变量
    var pos = -1;
    var pos1 = -1;
    var matchStr = "";
    var val = 0;
    var js = "";
    var splitchar = "";
    while(searchNext){
        try{
            matchStr = formatStr.match(searchStr);
            if(matchStr.length > 0){
                matchStr = matchStr[0];
                if(matchStr.length == 1){
                    //匹配到单个字符情况，需要考虑较多情况
                    pos = formatStr.indexOf(matchStr);
                    splitchar = formatStr.substring(pos+1,pos+2);
                    if(splitchar.match(/[^yMdhms]/) == null){
                        //没有分隔符的情况,只支持抓取第1个字符
                        val = parseInt(dateStr.substring(pos,pos+1));
                        dateStr = dateStr.substring(0,pos) + dateStr.substring(pos+1); //删除匹配上的内容
                    }
                    else{
                        //有分隔符的情况
                        pos1 = dateStr.indexOf(splitchar,pos);
                        val = parseInt(dateStr.substring(pos,pos1));
                        dateStr = dateStr.substring(0,pos) + dateStr.substring(pos1); //删除匹配上的内容
                    }
                }
                else{
                    //匹配到完整字符情况，可以直接以位置比对
                    pos = formatStr.indexOf(matchStr);
                    val = parseInt(dateStr.substring(pos,pos+matchStr.length));
                    dateStr = dateStr.substring(0,pos) + dateStr.substring(pos+matchStr.length); //删除匹配上的内容
                }
                js = "formatStr = formatStr.replace(/"+matchStr+"/,'');"; //删除本次匹配结果
                eval(js);
            }
            switch(matchStr){
                case "yyyy":
                case "yy":
                    dret.setYear(val);
                    searchStr = searchStr.replace("yyyy|yy","").trim("|").replace(/\|{2,}/g,"|");  //移除后再去头尾的|
                    break;
                case "MM":
                case "M":
                    dret.setMonth(val-1); //月份是从0开始
                    searchStr = searchStr.replace("MM|M","").trim("|").replace(/\|{2,}/g,"|");  //移除后再去头尾的|
                    break;
                case "dd":
                case "d":
                    dret.setDate(val);
                    searchStr = searchStr.replace("dd|d","").trim("|").replace(/\|{2,}/g,"|");  //移除后再去头尾的|
                    break;
                case "hh":
                case "h":
                    dret.setHours(val);
                    searchStr = searchStr.replace("hh|h","").trim("|").replace(/\|{2,}/g,"|");  //移除后再去头尾的|
                    break;
                case "mm":
                case "m":
                    dret.setMinutes(val);
                    searchStr = searchStr.replace("mm|m","").trim("|").replace(/\|{2,}/g,"|");  //移除后再去头尾的|
                    break;
                case "ss":
                case "s":
                    dret.setSeconds(val);
                    searchStr = searchStr.replace("ss|s","").trim("|").replace(/\|{2,}/g,"|");  //移除后再去头尾的|
                    break;
                default :
                    searchNext = false; //没有匹配到任何一个，结束匹配
                    break;
            }
        }
        catch(e){
            searchNext = false; //异常，结束匹配
        }
    }
    //返回
    return dret;
}

/*---------------
--timeBetween--
计算两个日期之间的时间差
--------------- */
function timeBetween(firstday,lastday,unit){
    //unit默认为d
    if(typeof unit == 'undefined'){
        unit = "d";
    }
    switch(unit){
        case "y":
            //年，先算整数部分
            var zs = lastday.getFullYear() - firstday.getFullYear();
            firstday.setYear(lastday.getFullYear());
            var xs = (lastday - firstday)/31536000000; //按一年有365天算
            return zs + xs;
        case "M":
            //月，再算月，再算天
            var yue = (lastday.getFullYear() - firstday.getFullYear())*12;
            firstday.setYear(lastday.getFullYear());
            yue = yue + (lastday.getMonth() - firstday.getMonth());
            if(firstday.getDate() < lastday.getDate()){
                //把月份也换成一样，由于存在2月28日的情况，需变化为日期多的月份
                firstday.setMonth(lastday.getMonth());
            }
            else{
                lastday.setMonth(firstday.getMonth());
            }
            var xs = (lastday - firstday)/2592000000;  //按一个月有30天计算
            return yue + xs;
        case "s": return (lastday - firstday)/1000;
        case "m": return (lastday - firstday)/60000;
        case "h": return (lastday - firstday)/3600000;
        case "w": return (lastday - firstday)/604800000;
        default :  return (lastday - firstday)/86400000;
    }
}

/*---------------
--add--
日期计算，获取增加指定单位时间的新日期
--------------- */
Date.prototype.add = function(timevalue,unit) {
    //unit默认为d
    if(typeof unit == 'undefined'){
        unit = "d";
    } 
　　var dtTmp = this 
　　switch (unit) { 
　　    case 's' :return new Date(Date.parse(dtTmp) + (1000 * timevalue)); 
　　    case 'm' :return new Date(Date.parse(dtTmp) + (60000 * timevalue)); 
　　    case 'h' :return new Date(Date.parse(dtTmp) + (3600000 * timevalue)); 
　　    case 'd' :return new Date(Date.parse(dtTmp) + (86400000 * timevalue)); 
　　    case 'w' :return new Date(Date.parse(dtTmp) + (604800000 * timevalue)); 
　　    case 'M' :
　　        //月份的情况，需考虑有小数的问题
　　         var newd = new Date(dtTmp.getFullYear(), (dtTmp.getMonth()) + parseInt(timevalue), dtTmp.getDate(), dtTmp.getHours(), dtTmp.getMinutes(), dtTmp.getSeconds()); 
　　         return new Date(Date.parse(newd) + (timevalue - parseInt(timevalue))*2592000000); 
　　    case 'y' :
　　        //年的情况，需考虑有小数的问题
　　        var newd = new Date((dtTmp.getFullYear() + parseInt(timevalue)), dtTmp.getMonth(), dtTmp.getDate(), dtTmp.getHours(), dtTmp.getMinutes(), dtTmp.getSeconds()); 
　　        //小数部分
　　        return new Date(Date.parse(newd) + (timevalue - parseInt(timevalue))*31536000000); 
　　    default : return new Date(Date.parse(dtTmp) + (86400000 * timevalue)); 
　　} 
} 

/*---------------
--maxOfMonth--
获得当前月的最大天数（最后一天的day值）
--------------- */
Date.prototype.maxOfMonth = function() {
    var day = new Date(this.getFullYear(),this.getMonth()+1,1);
    var day2 = day.add(-1,"d");
　　return day2.getDate(); 
}

/*---------------
--weekOfYear--
获得当前日期是当年的第几周
--------------- */
Date.prototype.weekOfYear = function() {
    var firstday = new Date(this.getFullYear(),0,1);  //一年中的第1天
    var lastday = new Date(this.getFullYear(),this.getMonth(),this.getDate()); //当天
    var begin;
    if(firstday.getDay() == 0){
        //1月1号是星期天
        begin = 1;
    }
    else{
        //找到第一个星期天
        firstday = firstday.add(7-firstday.getDay(),"d");
        begin = 2;
    }
    var weeks = parseInt(timeBetween(firstday,lastday,"w") + begin);  //用parseInt取整数
    return weeks;
}

/*---------------
--weekOfMonth--
获得当前日期是当月的第几周
--------------- */
Date.prototype.weekOfMonth = function() {
    var firstday = new Date(this.getFullYear(),this.getMonth(),1);  //一年中的第1天
    var lastday = new Date(this.getFullYear(),this.getMonth(),this.getDate()); //当天
    var begin;
    if(firstday.getDay() == 0){
        //1月1号是星期天
        begin = 1;
    }
    else{
        //找到第一个星期天
        firstday = firstday.add(7-firstday.getDay(),"d");
        begin = 2;
    }
    var weeks = parseInt(timeBetween(firstday,lastday,"w") + begin);  //用parseInt取整数
    return weeks;
}
