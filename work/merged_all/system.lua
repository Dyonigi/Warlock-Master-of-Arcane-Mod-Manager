-- мир
g_world = nil;

function globalSetWorld(world)
	g_world = world;
end;

#ifdef LOGS_ENABLED
#	define LogOut(...)        _LogOut
#	define ErrOut(...)        _ErrOut
#	define LogPushTab(...)	  _LogPushTab
#	define LogPopTab(...)	  _LogPopTab
#else
#	define LogOut(...)        
#	define ErrOut(...)        
#	define LogPushTab(...)
#	define LogPopTab(...)
#endif 	--#ifdef LOGS_ENABLED


-- полезные системные функции

function min( a , b )
	if ( a < b ) then return a;
	else return b; end;
end;

function max( a , b )
	if ( a < b ) then return b;
	else return a; end;
end;

LEVEL_0 = 0;
LEVEL_1 = 1;
LEVEL_2 = 2;
LEVEL_3 = 3;
LEVEL_4 = 4;


logLevel = LEVEL_2;

tabLevel = 0;
tabString = "";


function _LogPushTab()
    tabLevel = tabLevel + 1;
    tabString = string.rep("\t", tabLevel);
end;


function _LogPopTab()
    if (tabLevel > 0)
    then
        tabLevel = tabLevel - 1;

        if (tabLevel > 0)
        then
            tabString = string.rep("\t", tabLevel);
        else
            tabString = "";
        end;
    end;
end;


function _LogOut(level, message)
    if (type(level) ~= "number" or message == nil or (type(message) ~= "string"))
    then 
        SystemErrOut("\nINVALID SYNTAX: expected LogOut(level, message), but called LogOut('" .. level .. "', nil)\n");
        return;
    end;

    if (logLevel >= level)
    then
        SystemLogOut(tabString .. message);
    end;
end;

function _ErrOut(level, message)
    if (type(level) ~= "number" or message == nil or (type(message) ~= "string"))
    then 
        SystemErrOut("\nINVALID SYNTAX: expected ErrOut(level, message), but called ErrOut('" .. level .. "', nil)\n");
        return;
    end;

    if (logLevel >= level)
    then
        SystemErrOut(tabString .. message);
    end;
end;

function SortList(list, CmpFunc)
    local needSort = true;
    local iteration = 1;
    while (needSort) do
        local i = 1;
        needSort = false;
        while (list[i+1]) do
            if (CmpFunc(list[i], list[i+1]))
            then
                needSort = true;
                local temp = list[i];
                list[i] = list[i+1];
                list[i+1] = temp;
            end;
            i = i+1;
        end;
        iteration = iteration + 1;
    end;
end;                             
