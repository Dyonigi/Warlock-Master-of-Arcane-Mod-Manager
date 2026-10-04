--[[-------------------------------------------------
некоторые полезные функции:

Script:Log("message")
вывод сообщения в логи MOM2_Debug.log и Logic_Debug.log

Script:MessageBox("message")
вывод MessageBox

Lua math manual ( may be useful ):

math.abs math.acos math.asin math.atan math.atan2
math.ceil math.cos math.deg math.exp math.floor
math.log math.log10 math.max math.min math.mod
math.pow math.rad math.sin math.sqrt math.tan
math.frexp math.ldexp math.random math.randomseed

-------------------------------------------------]]--

-----------------------------------------------------
-- кол-во сообщений в логе
-- возможные значения (чем больше число, тем больше сообщений):
-- LEVEL_0 - не выводить логи
-- LEVEL_1 - важные сообщения, которые выводятся всегда, выводится очень мало логов
-- LEVEL_2 - стандартные сообщения, которые нужно выводить "обычно"
-- LEVEL_3 - более подробная информация, выводится много логов (отладочные)
-- LEVEL_4 - самая подробная ифнормация для отладки, выводится очень много логов
--
--
-- НЕ ЗАБЫВАЕМ! чтобы выводились логи, их нужно включить в ConfEdit
-----------------------------------------------------
logLevel = LEVEL_4;

--------------------------------------------------------
-- ВНИМАНИЕ! АХТУНК!
-- в связи с оптимизациями, внутри функций LogOut(...)
-- перенос парамеров ЗАПРЕЩЕН!
-- 
-- ТАК НЕЛЬЗЯ!
-- LogOut(LEVEL_1, "a=" .. a ..
--    " b=" .. b);
-- 
-- ТАК МОЖНО:
-- LogOut(LEVEL_1, "a=" .. a .. " b=" .. b);
-- 
-- или ТАК МОЖНО:
-- #ifdef LOGS_ENABLED
-- local msg = "a=" .. a .. " b=" .. b;
-- LogOut(LEVEL_1, msg);
-- #endif
--------------------------------------------------------

--------------------------------------------------------
-- дополнительные функции находятся в файле Utils.lua
--------------------------------------------------------

-----------------------------------------------------
-- глобальные понятия
-----------------------------------------------------

-- возможные направления юнита
DIR_FRONT = "Front";       -- фронт
DIR_FLANK = "Flank";       -- фланг
DIR_BACK = "Back";        -- тыл

-- тип боя
CLOSE_COMBAT = "CloseCombat";    	-- ближний бой
RANGED_COMBAT = "RangedCombat";   	-- дальний бой

-- роль в бою
ROLE_ATTACKER = "Attacker";
ROLE_DEFENDER = "Defender";

-- действие по умолчанию. специальная константа для автоопределения действия по  умолчаю
DEFAULT_ACTION = "_default";

-- константа для определения, что у нас магическая атака игрока
MAGIC_ATTACK = "__magic_attack_action";

-- специальная константа для установки флага иммунитета к атаке
REPORT_ATTACK_IMMUNE = 65535;

-- кто управляет юнитом - playerType
PLAYER_HUMAN = "HumanPlayer";
PLAYER_AI = "AiPlayer";


--[[

Инструкция: как к чему обращаться.
    
Поддерживающий юнит: юнит, который участвует в бою посредством поддержки. ?????????
пока нету

Владелец атаки: юнит, произведший атаку, которую мы сейчас обсчитываем.
combatants.attacker

Цель атаки: юнит, на который мы сейчас применим атаку, которую мы сейчас обсчитываем.
combatants.defender

Нападающий: юнит, который инициировал бой.

обратиться напрямую: battleInfo.attacker
проверить любой юнит: if (???:GetRole() == ROLE_ATTACKER)

Обороняющийся: юнит, который был выбран целью при иницииации боя

обратиться напрямую: battleInfo.defender
проверить любой юнит: if (???:GetRole() == ROLE_DEFENDER) 

например
if (combatants.attacker:GetRole() == ROLE_ATTACKER)   -- "если у нас владелец атаки - инициатор боя, то  ..."
if (combatants.defender:GetRole() == ROLE_ATTACKER)   -- "если у нас юнит, на который применяют атаку - инициатор боя, то ..."

т.е. в таком случае проверки бессмыслены:
if (battleInfo.attacker:GetRole() == ROLE_ATTACKER)    -- всегда будет true: "если у нас инициатор боя - инициатор боя, то  ..."
if (battleInfo.defender:GetRole() == ROLE_ATTACKER)    -- никогда не будет true: "если у нас обороняющийся - инициатор боя, то  ..."

Внимание! так делать НЕЛЬЗЯ - не будет работать! (не поддерживается нашими скриптами, хотя вполне осмысленно)

if (combatants.attacker == battleInfo.attacker)      -- НЕЛЬЗЯ!
if (combatants.attacker:GetRole() == ROLE_ATTACKER)     -- можно

Юнит игрока-человека или компьютера?
if (combatants.attacker:PlayerType() == PLAYER_AI)     	-- атакующий - юнит компьютера
if (combatants.attacker:PlayerType() == PLAYER_HUMAN)    -- атакующий - юнит игрока

получить уровень сложности
local diff = g_world:GetDifficulty();

пользуемся как-то так:
if (combatants.attacker:PlayerType() == PLAYER_AI)  damage = damage * diff.enemyDamageK;

]]--    

-----------------------------------------------------
-- глобальные параметры
-----------------------------------------------------
battleGlobal = {};

-- использовать случайные числа для повреждений (default: true) 
battleGlobal.variateHPs = true;

-- для отладки оступления - побежденный всегда отступает если он проиграл в ближнем бою (default: false) 
battleGlobal.alwaysRetreat = false;


-----------------------------------------------------
-- вспомогательные функции
-----------------------------------------------------
function Random()
	if (battleGlobal.variateHPs)
	then
		return g_world:getNextRandom();
	else
		return 0.5;
	end;
end;



-----------------------------------------------------
-- считаем вероятность нанесения критикалов. критикалы действуют на все атаки
-- важно! критикалы работают только для нападающего юнита!
-----------------------------------------------------
function CalculateCriticals(battleInfo, report)

	-- коэффициент умножения. 1.0 - без изменений, 2.0 - удвоенный вред
	battleInfo.attackerCriticalK = 1;

	local probability = 0.2; -- elm 2011-06-27: вероятность критикала у всех 20%
	local power = 1.5; -- elm 2011-06-27: сила критикала уменьшена с 2 до 1.5


	-- применяем уровни сложности
	if (battleInfo.defender:PlayerType() == PLAYER_HUMAN)	
	then
		local diff = g_world:GetDifficulty();
		probability = probability * diff.enemyCriticalK;
	end;

    LogOut(LEVEL_2, "Criticals - probability: " .. string.format("%.2f", probability));

	-- случилось?
	local isCritical = Random() < probability; 

	-- возможно, здесь мы потом захотим влиять на критикал перками атакующего и обороняющегося

	--isCritical = true;

	if (isCritical)
	then
		battleInfo.attackerCriticalK = power;
	    LogOut(LEVEL_2, "Criticals - result: HIT, attackerCriticalK=" .. string.format("%.2f", battleInfo.attackerCriticalK));
	else
	    LogOut(LEVEL_2, "Criticals - result: FAILED");
	end;


	-- пишем в отчет для истории
	report:SetCriticalDamage(isCritical);
end;

                            

-----------------------------------------------------
-- Понятие противоборствующих юнитов в бою. нужно для удобной итерации по юнитам в общем случае.
-----------------------------------------------------
function MakeCombatants(attacker, defender, attackerId, defenderId)

	tempTable = {};
	tempTable.attacker = attacker;
	tempTable.defender = defender;
	tempTable.attackerId = attackerId;
	tempTable.defenderId = defenderId;
	tempTable.defBuildingK = 1.0;		-- эесли бой в городе - корректируем коэффициенты
	return tempTable;
end;

-----------------------------------------------------
-- подготовить глобальную информацию о бое
-----------------------------------------------------
function MakeBattleInfo(actionName, attacker, defender, defCover, dumpInfo)
    battleInfo = {};

    -- наши юниты
    battleInfo.attacker = attacker;
    battleInfo.defender = defender;

	battleInfo.attackerId = attacker:GetObjectID();
	battleInfo.defenderId = defender:GetObjectID();

	battleInfo.magicAttack = (actionName == MAGIC_ATTACK);
	
	-- в этой переменной будем хранить инициативу
	battleInfo.currentInitiative = 0;

	battleInfo.unitCombatants = {};

	-- помещаем в таблицу главные противоборствующие стороны - для удобства
	battleInfo.unitCombatants[1] = MakeCombatants(battleInfo.attacker, battleInfo.defender, battleInfo.attackerId, battleInfo.defenderId);

	local isRangedAttack = false;

	if (battleInfo.magicAttack)
	then
		isRangedAttack = true;
		battleInfo.battleRange = 0;
	else
		battleInfo.unitCombatants[2] = MakeCombatants(battleInfo.defender, battleInfo.attacker, battleInfo.defenderId, battleInfo.attackerId);

	    -- дистанция боя
    	battleInfo.battleRange = g_world:GetDistanceBetween(attacker, defender);

		-- атакующий дает в глаз с помощью указанного экшена
		attacker:SetCurrentAction(actionName);

		-- определяем, это стрелковый бой или нет
		-- признак, что у атакующего - только стрелковая атака
		local action = attacker:GetCurrentAction();
		isRangedAttack = action:IsRangedCombat();
	end;

	-- если враг в городе - увы, получает бонус за вредность. а город огребает
	if (defCover ~= nil)
	then
		battleInfo.defCover = defCover;
		battleInfo.defCoverId = defCover:GetObjectID();

		battleInfo.defCover:SetCurrentAction(DEFAULT_ACTION);

		-- защищающийся получает уменьшенный вред
		battleInfo.unitCombatants[1].defBuildingK = 0.5;

		-- здание получает уменьшенный вред
		battleInfo.unitCombatants[3] = MakeCombatants(battleInfo.attacker, battleInfo.defCover, battleInfo.attackerId, battleInfo.defCoverId);
		battleInfo.unitCombatants[3].defBuildingK = 0.5;

		-- здание отвечает
		battleInfo.unitCombatants[4] = MakeCombatants(battleInfo.defCover, battleInfo.attacker, battleInfo.attackerId, battleInfo.defCoverId);
	else
		battleInfo.defCover = nil;
		battleInfo.defCoverId = nil;
	end;

	-- защищающийся обороняется default экшеном
	defender:SetCurrentAction(DEFAULT_ACTION);

	if (isRangedAttack)
	then
		-- дальний бой
		battleInfo.missileAttack = true;
		battleInfo.battleType = RANGED_COMBAT;
		battleInfo.attackFrom = DIR_FRONT;
	else
		-- ближний бой
		battleInfo.missileAttack = false;
		battleInfo.battleType = CLOSE_COMBAT;

		-- направление удара по защищающемуся - один из DIR_XXXX
		battleInfo.attackFrom = defender:GetSideFor(attacker);
	end;

    if (dumpInfo)
    then
        LogOut(LEVEL_2, "Attacker: " .. tostring(battleInfo.attacker));
        LogOut(LEVEL_2, "Defender: " .. tostring(battleInfo.defender));
        LogOut(LEVEL_2, "battleRange: " .. battleInfo.battleRange);
        LogOut(LEVEL_2, "battleType: " .. battleInfo.battleType);
        LogOut(LEVEL_2, "attackFrom: " .. tostring(battleInfo.attackFrom));
        LogOut(LEVEL_2, "missileAttack: " .. tostring(battleInfo.missileAttack));
        LogOut(LEVEL_2, "diffuculty: " .. g_world:GetDifficulty().name);
        if (battleInfo.defCover ~= nil)
        then
	        LogOut(LEVEL_2, "Defender cover: " .. tostring(battleInfo.defCover));
        end;
        LogOut(LEVEL_2, "");
    end;

    return battleInfo;
end;



-----------------------------------------------------
-- влияние хитпоинтов
-----------------------------------------------------
function CalculateHitPointsK(battleInfo, unit)

	local curHP = unit:GetAliveHP();
	local maxHP = unit:GetTotalHP();

    LogOut(LEVEL_2, "attacker HP=" .. curHP .. " /" .. maxHP);

	local result = 0.10	+ 0.90 * curHP / maxHP;
	return result;
end;


-----------------------------------------------------
-- поулчить устойчивость к типу атаки в виде коэффициента
-----------------------------------------------------
function GetResistanceK(battleInfo, unit, attack)

	-- суммарная устойчивость с учетом всех перков
	local resist = unit:GetResistance(attack.damageType);

	-- magic formula ПРИ ИЗМЕНЕНИИ ФОРМУЛЫ НАДО ДУБЛИРОВАТЬ У КАТАРИНЫ И ДИМАТА (ттх юнитов и предсказание боя)
	local resistK = math.pow(2, resist / -50);	

    LogOut(LEVEL_2, "defender resist=" .. resist .. "  resistK=" .. string.format("%.2f", resistK));

	return resistK;
end;



-----------------------------------------------------
-- применяем ландшафт
-----------------------------------------------------
function CalculateTerrainK(battleInfo, combatants, report)
    
    local attackerK = 1;
    -- local defenderK = 1;

    -- вспомогательная проверка "юнит находится в лесу"
    local InTheForest = function(unit)
        local landType = g_world:GetUnitLandType(unit);
        return landType == "Dense" or landType == "HighDense";
    end;

    -- вспомогательная проверка "юнит находится на холме"
    local OnTheHills = function(unit)
        local landType = g_world:GetUnitLandType(unit);
        return landType == "High" or landType == "HighDense";
    end;

    -- вспомогательная проверка "юнит находится на плохом ландшафте"
    local IsBadTerrain = function(unit)
        local landType = g_world:GetUnitLandType(unit);
        return landType == "Bad";
    end;

    -- вспомогательная проверка "юнит находится в укреплениях"
    local InFortifications = function(unit)

        -- пока не определились, что же есть укрепления
        return false;
    end;

    -- ВНИАМАНИЕ! Добавлять новые типы бонусов (используя RegisterBonus) атаки только вместе с программистами!
    -- проверяем условия:

    -- Холм
    -- Холм дает защиту всем, кто на нем стоит, кроме случая: нападающий в рукопашном бою. 
    -- Кроме того, холм не защищает от летунов и (возможно) магии игрока.
    if (OnTheHills(combatants.defender) and -- Холм дает защиту всем, кто на нем стоит,
    	not (combatants.defender:GetRole() == ROLE_ATTACKER and combatants.defender:GetMovementType() == "Walker" and battleInfo.battleType == CLOSE_COMBAT) and -- кроме случая: нападающий в рукопашном бою
    	(combatants.attacker:GetMovementType() == "Walker" or combatants.attacker:GetMovementType() == "Naval" or combatants.attacker:GetMovementType() == "Amphibious")) -- Кроме того, холм не защищает от летунов и (возможно) магии игрока
   	then
        LogOut(LEVEL_3, "--- [Hill defense bonus!]: attack x0.75");

        report:RegisterBonus(combatants.attacker:GetRole(), "HillDefense", 0.75);
        attackerK = attackerK * 0.75;
    else  -- Упс! Теперь у нас влияет или холм или лес, но не оба. Это сделано, чтобы лесистые холмы не получали аномально высокий бонус за счет перемножения коэффициентов.

	-- Лес
	-- Лес дает защиту всем, кроме случая: нападающий в рукопашном бою.
	    if (InTheForest(combatants.defender) and -- Лес дает защиту всем,
    		not (combatants.defender:GetRole() == ROLE_ATTACKER and combatants.defender:GetMovementType() == "Walker" and battleInfo.battleType == CLOSE_COMBAT)) -- кроме случая: нападающий в рукопашном бою                                 
	   	then
	        LogOut(LEVEL_3, "--- [Forest defense bonus!]: attack x0.75");

	        report:RegisterBonus(combatants.attacker:GetRole(), "ForestDefense", 0.75);
	        attackerK = attackerK * 0.75;
   		end;
   	end;


   	-- Плохой ландшафт
   	-- В плохом ландшафте пенальти к защите всегда, кроме летунов и амфибий (?).
    if (IsBadTerrain(combatants.defender) and -- В плохом ландшафте пенальти к защите всегда,
    	not (combatants.defender:GetMovementType() == "Flyer"  or combatants.defender:GetMovementType() == "Amphibious")) -- кроме летунов и амфибий
   	then
        LogOut(LEVEL_3, "--- [Bad terrain defense penalty!]: attack x1.5");

        report:RegisterBonus(combatants.attacker:GetRole(), "BadTerrainDefense", 1.5);
		attackerK = attackerK * 1.5;
   	end;

   	-- Река
   	-- Здесь будет обработка атаки через реку: в рукопашном бою Нападающий (если он не амфибия и не летун) наносит меньше потерь, а получает больше.
   	-- Что-то про River :)

   	-- Укрепления
   	-- Fortifications
   	-- Нахождение в боевом здании (фортификации) дает бонус в другом месте: все входящие атаки наносятся и зданию и юниту, но их сила снижается вдвое 
   	-- (т.е. атака как бы делится между ними поровну).

    -- Дополнительный урон Нападающему в неблагоприятных условиях.
    -- Нападающий врукопашную юнит получает дополнительный урон от всех входящих атак, если находится в одной из неблагоприятных ситуаций: 
    -- вверх по холму, через реку, (и другие, когда мы о них вспомним). Эта пенальти не распространяется на летунов (и в случае с рекой - на амфибий).

    if (combatants.defender:GetRole() == ROLE_ATTACKER and battleInfo.battleType == CLOSE_COMBAT and -- Нападающий врукопашную юнит получает дополнительный урон, если 
    	( 
    		(not OnTheHills(combatants.defender) and OnTheHills(combatants.attacker) and -- вверх по холму, 
    		combatants.defender:GetMovementType() ~= "Flyer" and -- причем это пенальти не распространяется на летунов
    		not combatants.defender:HasStatus("highlander"))-- а еще это пенальти не распространяется на горцев
    		--or 
    		--() -- через реку (если мы это не обситывали чуть выше)
    	))
    then
        LogOut(LEVEL_3, "--- [Difficult attack penalty!]: attack x1.5");

        report:RegisterBonus(combatants.attacker:GetRole(), "DifficultAttack", 1.5);
        attackerK = attackerK * 1.5;
    end;

    -----------------------
    -- Unit-specific бонусы 
    -----------------------

    -- "Лесники" :) - юниты, у который в перках имеется признак "Forester"
    -- Лесники всегда получают меньше урона, если находятся в лесу
    if (combatants.defender:HasStatus("forester") and InTheForest(combatants.defender))
    then
        LogOut(LEVEL_3, "--- [Foresters hide in woods!]: attack x0.75");

        report:RegisterBonus(combatants.attacker:GetRole(), "ForesterDefenseInWood", 0.75);
        attackerK = attackerK * 0.75;
    end;

	-- cover - Бонус к защите в любой местности
    if (combatants.defender:HasStatus("cover") and (InTheForest(combatants.defender) or OnTheHills(combatants.defender) or IsBadTerrain(combatants.defender)))
    then
        LogOut(LEVEL_3, "--- [Taking cover!]: attack x0.75");

        report:RegisterBonus(combatants.attacker:GetRole(), "TakingCover", 0.75);
        attackerK = attackerK * 0.75;
    end;

	-- cityfighter - бонус, если стоим в здании
    if (combatants.defender:HasStatus("cityfighter") and g_world:HasAnyBuildingAt(combatants.defender:GetPosition()))
    then
        LogOut(LEVEL_3, "--- [Taking cover in building!]: attack x0.75");

        report:RegisterBonus(combatants.attacker:GetRole(), "TakingCoverInBuilding", 0.75);
        attackerK = attackerK * 0.75;
    end;

	-- Лесники наносят больше урона по целям, находящимся в лесу, но только если цель - не летун
    if (combatants.attacker:HasStatus("forester") and InTheForest(combatants.defender) and combatants.defender:GetMovementType() ~= "Flyer")
    then
        LogOut(LEVEL_3, "--- [Foresters hunt down enemies in woods!]: attack x1.25");

        report:RegisterBonus(combatants.attacker:GetRole(), "ForesterAttackInWood", 1.25);
		attackerK = attackerK * 1.25;
    end;

	-- cityfighter - бонус, если атакуем юнит в здании
    if (combatants.attacker:HasStatus("cityfighter") and g_world:HasAnyBuildingAt(combatants.defender:GetPosition()) and combatants.defender:GetMovementType() ~= "Flyer")
    then
        LogOut(LEVEL_3, "--- [Cityfighters hunt down enemies in town!]: attack x1.25");

        report:RegisterBonus(combatants.attacker:GetRole(), "Cityfighter", 1.25);
        attackerK = attackerK * 1.25;
    end;

	-- siege - бонус, если атакуем здание
    if (combatants.attacker:HasStatus("siege") and combatants.defender:GetMovementType() == "Static")
    then
        LogOut(LEVEL_3, "--- [siege - bonus vs building!]: attack x2.0");

        report:RegisterBonus(combatants.attacker:GetRole(), "Siege", 2);
        attackerK = attackerK * 2.0;
    end;

    -- "Горцы"
    -- Горцы всегда получают меньше урона, если находятся на холме
    if (combatants.defender:HasStatus("highlander") and OnTheHills(combatants.defender))
    then
        LogOut(LEVEL_3, "--- [Highlanders use cover in hills!]: attack x0.75");

        report:RegisterBonus(combatants.attacker:GetRole(), "HighlanderDefenseInHill", 0.75);
        attackerK = attackerK * 0.75;
    end;

	-- Горцы наносят больше урона по целям, находящимся на холмах, но только если цель - не летун
    if (combatants.attacker:HasStatus("highlander") and OnTheHills(combatants.defender) and combatants.defender:GetMovementType() ~= "Flyer")
    then
        LogOut(LEVEL_3, "--- [Highlanders ambush enemy in hills!]: attack x1.25");

        report:RegisterBonus(combatants.attacker:GetRole(), "HighlanderAttackInHill", 1.25);
        attackerK = attackerK * 1.25;
    end;


	-- Юнит в защите: уменьшает потери юнита от любого урона в 1.5 раза
    if (combatants.defender:HasStatus("in_defence"))
	then
        LogOut(LEVEL_3, "--- [Defending unit in defence!]: attack x2/3");

        report:RegisterBonus(combatants.attacker:GetRole(), "InDefence", 2.0 / 3.0);
        attackerK = attackerK * 2.0 / 3.0;
	end;

	-- Юнит ненавидит противника
	if (combatants.attacker:HatredUnit(combatants.defender))
	then
        LogOut(LEVEL_3, "--- [Attacker unit hatred defence!]: attack x1.5");

        report:RegisterBonus(combatants.attacker:GetRole(), "Hatred", 1.5);
        attackerK = attackerK * 1.5;
	end;

	
   	--[[  OLD
    -- Нелетающий юнит, атакуемый дистанционно и находящийся в лесу получает бонус "In cover!"
    if (battleInfo.battleType == RANGED_COMBAT and combatants.defender:GetMovementType() ~= "Flyer" and InTheForest(combatants.defender))
    then
        LogOut(LEVEL_3, "+++ [In cover!]: defence x2");
        defenderK = defenderK * 2;
    end;

    -- Наземный юнит, сражается в ближнем бою, находится не на холме, причем противник на холме. 
    -- Юнит получает пенальти "Uphill battle!"
    if (battleInfo.battleType == CLOSE_COMBAT and 
        combatants.attacker:GetMovementType() == "Walker" and not OnTheHills(g_world, combatants.attacker) and OnTheHills(combatants.defender))
    then
        LogOut(LEVEL_3, "--- [Uphill battle!]: attack x0.75");
        attackerK = attackerK * 0.75;
    end;

    if (battleInfo.battleType == CLOSE_COMBAT and 
        combatants.defender:GetMovementType() == "Walker" and not OnTheHills(g_world, combatants.defender) and OnTheHills(combatants.attacker))
    then
        LogOut(LEVEL_3, "--- [Uphill battle!]: defence x0.75");
        defenderK = defenderK * 0.75;
    end;

    -- Ближний бой. Юнит с классом "конница" атакует противника, находящегося в лесу; 
    -- либо же Юнит с классом "конница" обороняется, находясь в лесу. Юнит получает пенальти "Cavalry in Woods!"
    if (battleInfo.battleType == CLOSE_COMBAT and 
        combatants.attacker:GetUnitClass() == "Cavalry" and InTheForest(combatants.defender))
    then
        LogOut(LEVEL_3, "--- [Cavalry in Woods!]: attack x0.5");
        attackerK = attackerK * 0.5;
    end;

    if (battleInfo.battleType == CLOSE_COMBAT and 
        combatants.defender:GetUnitClass() == "Cavalry" and InTheForest(combatants.defender))
    then
        LogOut(LEVEL_3, "--- [Cavalry in Woods!]: defence x0.5");
        defenderK = defenderK * 0.5;
    end;

    -- Летающий юнит, атакующий противника в ближнем бою, находящегося в лесу, получает пенальти "Flyer Hindrance!"
    if (battleInfo.battleType == CLOSE_COMBAT and 
        combatants.attacker:GetMovementType() == "Flyer" and InTheForest(combatants.defender))
    then
        LogOut(LEVEL_3, "--- [Flyer Hindrance!]: attack x0.5");
        attackerK = attackerK * 0.5;
    end;

    -- Наземный юнит, находящийся в овраге, болоте (или другом "плохом" ландшафте, список составим), 
    -- сражающийся в ближнем бою, получает пенальти "Difficult Terrain!"
    if (battleInfo.battleType == CLOSE_COMBAT and 
        combatants.attacker:GetMovementType() == "Walker" and IsBadTerrain(combatants.attacker))
    then
        LogOut(LEVEL_3, "--- [Difficult Terrain!]: attack x0.5");
        attackerK = attackerK * 0.5;
    end;

    if (battleInfo.battleType == CLOSE_COMBAT and 
        combatants.defender:GetMovementType() == "Walker" and IsBadTerrain(combatants.defender))
    then
        LogOut(LEVEL_3, "--- [Difficult Terrain!]: defence x0.5");
        defenderK = defenderK * 0.5;
    end;

    -- Ближний бой. Юнит с классом "скирмишеры" атакует противника, находящегося в лесу; 
    -- либо же Юнит с классом "скирмишеры" обороняется в лесу. Юнит получает бонус "Forest Ambush!" 
    if (battleInfo.battleType == CLOSE_COMBAT and 
        combatants.attacker:GetUnitClass() == "Skirmish" and InTheForest(combatants.defender))
    then
        LogOut(LEVEL_3, "+++ [Forest Ambush!]: attack x2");
        attackerK = attackerK * 2.0;
    end;

    if (battleInfo.battleType == CLOSE_COMBAT and 
        combatants.defender:GetUnitClass() == "Skirmish" and InTheForest(combatants.defender))
    then
        LogOut(LEVEL_3, "+++ [Forest Ambush!]: defence x2");
        defenderK = defenderK * 2.0;
    end;

    -- Обороняющийся юнит в укреплениях получает бонус "Fortifications!"
    if (InFortifications(combatants.defender))
    then
        LogOut(LEVEL_3, "+++ [Fortifications!]: defence x2");
        defenderK = defenderK * 2.0;
    end;
    ]]--
    return attackerK; -- * defenderK;
end;


-----------------------------------------------------
-- влияние статусов юнита (кроме как за ландшафт)
-----------------------------------------------------
function CalculateStatusK(battleInfo, combatants, report)

    local attackerK = 1;

    if (combatants.attacker:HasStatus("finisher"))
    then
		local curHP = combatants.defender:GetAliveHP();
		local maxHP = combatants.defender:GetTotalHP();

		local hpPercent = 1.0 * curHP / maxHP;

		if (hpPercent < 0.5)
		then
        	LogOut(LEVEL_3, "--- [Attacker unit is finisher!]: attack x1.3");

    	    report:RegisterBonus(combatants.attacker:GetRole(), "Finisher", 1.3);

			attackerK = attackerK * 1.3;	
		end;
	end;

	return attackerK;
end;

-----------------------------------------------------
-- провести одну атаку для пары (атакующий бьет защищающегося)
-----------------------------------------------------
function ApplyAttack(battleInfo, combatants, attack, report)

    LogOut(LEVEL_2, tostring(combatants.attacker) .. " -> " .. tostring(combatants.defender) .. ", [" .. attack.damageType .. " " .. attack.actionType .. "]");

    LogPushTab();

	-- проверяем иммунитет. если иммунитет - атака не наносит вреда (хаха!). пишем в репорт это и радостно закругляемся.
	local immune = combatants.defender:IsImmunity(attack.damageType);

	-- сила атаки, с учетом всех перков
	local attackPower = attack.power;

	-- коэффициент уменьшения урона по юнитам в городе (если без города - то 1.0)
	local coverK = combatants.defBuildingK;

	-- применяем влияние хитпоинтов
	local hitpointsK = CalculateHitPointsK(battleInfo, combatants.attacker);

	-- применяем модификаторы за ландшафт
	local landscapeK = CalculateTerrainK(battleInfo, combatants, report);

	-- применяем резисты защитника
	local resistK = GetResistanceK(battleInfo, combatants.defender, attack);

	-- применяем модификаторы за статусы (кроме как за ландшафт)
    local statusK = CalculateStatusK(battleInfo, combatants, report);

	-- коэффициент урона по юнитам фракции игрока
	local diffK = 1.0;
	if (combatants.defender:PlayerType() == PLAYER_HUMAN)
	then
		local diff = g_world:GetDifficulty();
		diffK = diff.enemyDamageK;
	end;

	-- рандомизируем потери
	local maxDeviation = 0.2; -- например, 0.2 означает, что потери могут отличаться на +/- 20%
	local randomK = 1 + maxDeviation * (1 - 2 * Random());

	-- критикалы - только если атакуем именно мы
	local criticalK;
	if (combatants.attacker:GetRole() == ROLE_ATTACKER)
	then
		criticalK = battleInfo.attackerCriticalK;
	else
		criticalK = 1;
	end;

	-- Вычисляем силу атаки, которая будет показана в предсказании боя
   	local showAttackPower = attackPower * coverK * hitpointsK * diffK;

   	if (immune)
	then
		-- отчитаемся об этом позоре
		report:RegisterAttack(attack, combatants.attackerId, combatants.defenderId, battleInfo.currentInitiative, REPORT_ATTACK_IMMUNE, showAttackPower, 1.0);

	    LogPopTab();
	    LogOut(LEVEL_2, "[" .. attack.damageType .. " " .. attack.actionType .. "] --> IMMUNITET!");
		return 0;
	end;

	-- момент истины
	local resultPower = showAttackPower * landscapeK * resistK * statusK * randomK * criticalK;

#ifdef LOGS_ENABLED
	local msg = string.format(
        "power(%.1f) = pSrc(%.2f) * cover(%.2f) * hp(%.2f) * land(%.2f) * resist(%.2f) * diff(%.2f)\n" .. 
		"    * status(%.2f) * random(%.2f) * critical(%.2f)",
        resultPower, 
		attackPower,
		coverK,
		hitpointsK,
        landscapeK,
        resistK,
		diffK,
		statusK,
		randomK,
		criticalK
        );

    LogOut(LEVEL_3, msg);
#endif	--LOGS_ENABLED

    LogPopTab();

	-- лечиться не будем в любом случае...
	local resultPower = math.max(0, resultPower);

	-- мы его убьем, его убьем! наверное...
	lostHitPoints = combatants.defender:AccumulateDamage(resultPower);
    LogOut(LEVEL_2, "[" .. attack.damageType .. " " .. attack.actionType .. "] --> lostHP=" .. lostHitPoints);

	-- отчитаемся о проделанной работе
	report:RegisterAttack(attack, combatants.attackerId, combatants.defenderId, battleInfo.currentInitiative, lostHitPoints, showAttackPower, resistK);

	return lostHitPoints;
end;



-----------------------------------------------------
-- применить все атаки одного юнита на другой
-----------------------------------------------------
function DoAttacks(battleInfo, combatants, report, canActionBeApplied)

	local action = combatants.attacker:GetCurrentAction();
	if (not battleInfo.magicAttack and not canActionBeApplied)
	then
	    LogOut(LEVEL_2, tostring(combatants.attacker) .. " -> " .. tostring(combatants.defender) .. ", action DISABLED");
		return;
	end;

	local attackCount = combatants.attacker:GetAttackCount();

	for index = 0, attackCount - 1 , 1 do
		local attack = combatants.attacker:GetAttack(index);

	    -- вычисляем количество потерь, нанесенных каждой атакой
		ApplyAttack(battleInfo, combatants, attack, report);
	    LogOut(LEVEL_3, "");
	end;
end;

-----------------------------------------------------
-- применить использование action-а, если необходимо
-----------------------------------------------------
function ApplyUseActions(battleInfo, combatants, canActionBeApplied)

	if (not battleInfo.magicAttack and not canActionBeApplied)
	then
		return;
	end;

	local defenderDisbanded = combatants.defender:IsDisbanded();
	if (not (combatants.attacker:HasStatus("frenzy") and defenderDisbanded))
	then
		combatants.attacker:UseCurrentAction();
	end;

end;


function ForecastBattle(attacker, defender, defCover, actionName, report)
	-- Выключаем рандомизацию
	local beforeVariateHPs = battleGlobal.variateHPs;
	battleGlobal.variateHPs = false;

	local result = Battle(attacker, defender, defCover, actionName, report);

	-- Восстанавливаем рандомизацию
	battleGlobal.variateHPs = beforeVariateHPs;
	return result;
end;

-----------------------------------------------------
-- основная функция битвы
-----------------------------------------------------
function Battle(attacker, defender, defCover, actionName, report)

    LogOut(LEVEL_1, "\n----> Battle: begin...");

	-- вывод стартовой информации
    LogOut(LEVEL_2, "Attacker: " .. UnitBeginInfo(attacker));
    LogOut(LEVEL_2, "Defender: " .. UnitBeginInfo(defender));
    LogOut(LEVEL_2, "");

	LogPushTab();

    -- начало боя - настройка глобальных параметров
    battleInfo = MakeBattleInfo(actionName, attacker, defender, defCover, true);

	-- начальное состояние
	local attackerStartHP = attacker:GetAliveHP();
	local defenderStartHP = defender:GetAliveHP();
	local coverStartHP = 0;
	if (battleInfo.defCover ~= nil)
	then
		coverStartHP = battleInfo.defCover:GetAliveHP();
	end;

    -- считаем вероятность нанесения критикалов. критикалы действуют на все атаки
	CalculateCriticals(battleInfo, report);

    -- пока одна инициатива. например, 10я. потому что хорошее число.
	battleInfo.currentInitiative = 10;
	report:RegisterInitiative(battleInfo.currentInitiative);

	-- стоим в замке? он тоже получит свой паек на сегодня. причем сначала, чтобы защищающийся еще не ослабил атакующего
	local lostCover = 0;
	if (battleInfo.defCover ~= nil)
	then
		local attToCoverCombatants = battleInfo.unitCombatants[3];
		local attFromCoverCombatants = battleInfo.unitCombatants[4];

		local attToCoverAction = attToCoverCombatants.attacker:GetCurrentAction();
		local attFromCoverAction = attFromCoverCombatants.attacker:GetCurrentAction();

		local attToCoverCanApplied = CanActionBeApplied(battleInfo, attToCoverAction, attToCoverCombatants, false);
		local attFromCoverCanApplied = CanActionBeApplied(battleInfo, attFromCoverAction, attFromCoverCombatants, false);

		-- атакуем здание
		DoAttacks(battleInfo, attToCoverCombatants, report, attToCoverCanApplied);

		-- ОНО отвечает
		DoAttacks(battleInfo, attFromCoverCombatants, report, attFromCoverCanApplied);

		-- применяем полученные потери
		battleInfo.defCover:ApplyDamage(false);

		ApplyUseActions(battleInfo, attToCoverCombatants, attToCoverCanApplied);
		ApplyUseActions(battleInfo, attFromCoverCombatants, attFromCoverCanApplied);

		-- выявление победившего и наказание проигравшего
		local coverEndHP = defCover:GetAliveHP();
		lostCover = coverStartHP - coverEndHP;

	    -- в конце боя заполняем статистику
		report:SetBeforeHP(battleInfo.defCoverId, coverStartHP);
		report:SetLostHP(battleInfo.defCoverId, lostCover);
		report:SetDisbanded(battleInfo.defCoverId, battleInfo.defCover:IsDisbanded());
	end;

	local attToDefCombatants = battleInfo.unitCombatants[1];
	local attFromDefCombatants = battleInfo.unitCombatants[2];

	local attToDefAction = attToDefCombatants.attacker:GetCurrentAction();
	local attFromDefAction = attFromDefCombatants.attacker:GetCurrentAction();

	local attToDefCanApplied = CanActionBeApplied(battleInfo, attToDefAction, attToDefCombatants, false);
	local attFromDefCanApplied = CanActionBeApplied(battleInfo, attFromDefAction, attFromDefCombatants, false);

	-- сначала применяем все атаки атакующего
	DoAttacks(battleInfo, attToDefCombatants, report, attToDefCanApplied);

	-- потом применяем все атаки защищающегося
	DoAttacks(battleInfo, attFromDefCombatants, report, attFromDefCanApplied);

	-- применяем полученные потери
	battleInfo.attacker:ApplyDamage(false);
	local defenderEscaped = battleInfo.defender:ApplyDamage(true);

	ApplyUseActions(battleInfo, attToDefCombatants, attToDefCanApplied);
	ApplyUseActions(battleInfo, attFromDefCombatants, attFromDefCanApplied);

	-- выявление победившего и наказание проигравшего
	local attackerEndHP = attacker:GetAliveHP();
	local defenderEndHP = defender:GetAliveHP();

	local lostAttacker = attackerStartHP - attackerEndHP;
	local lostDefender = defenderStartHP - defenderEndHP;

	-- победившая сторона
	local victorySide = "";
	if ((lostAttacker / attackerStartHP) < (lostDefender / defenderStartHP))
	then
	    victorySide = ROLE_ATTACKER;
	else
	    victorySide = ROLE_DEFENDER;
	end;

    -- в конце боя заполняем статистику
    report:SetVictorySide(victorySide);
	report:SetBattleType(battleInfo.battleType);

	report:SetBeforeHP(battleInfo.attackerId, attackerStartHP);
	report:SetBeforeHP(battleInfo.defenderId, defenderStartHP);

	report:SetLostHP(battleInfo.attackerId, lostAttacker);
    report:SetLostHP(battleInfo.defenderId, lostDefender);

	local attackerDisbanded = attacker:IsDisbanded();
	local defenderDisbanded = defender:IsDisbanded();

	report:SetDisbanded(battleInfo.attackerId, attackerDisbanded);
	report:SetDisbanded(battleInfo.defenderId, defenderDisbanded);

	-- учитываем вампиризм
	if (not attackerDisbanded) then
		local attMaxRepairHP = attacker:GetTotalHP() - attackerEndHP;
		local attRepairHP = math.min(lostDefender * attacker:getVampirism(), attMaxRepairHP);
		report:setRepairHP(battleInfo.attackerId, attRepairHP);
		battleInfo.attacker:ApplyRepair(attRepairHP);
	end;

	if (not defenderDisbanded) then
		local defMaxRepairHP = defender:GetTotalHP() - defenderEndHP;
		local defRepairHP = math.min(lostAttacker * defender:getVampirism(), defMaxRepairHP);
		report:setRepairHP(battleInfo.defenderId, defRepairHP);
		battleInfo.defender:ApplyRepair(defRepairHP);
	end;

    -- вычисляем и устанавливаем линию видимости
--  report:SetLOS(g_world:GetLineOfSight(attacker, defender));

	-- frenzy - Нерасход очков движения, если вражеский юнит убит в бою
	-- hitAndRun - Нерасход очков движения в любом случае
	if (attacker:HasStatus("frenzy") and defenderDisbanded) 
	then
	    LogOut(LEVEL_2, "Attacker: frenzy - enemy disbanded - no movement points spent!");
	elseif attacker:HasStatus("hitAndRun") then
		-- всё же расходуем немного очков движения (чтобы отвалилась возможность defend-а)
		attacker:SetMovePoints(math.max(attacker:GetMovePoints() - 0.5, 0.0));
	    LogOut(LEVEL_2, "Attacker: hitAndRun - no movement points spent!");
	else
		attacker:SetMovePoints(0.0);
	end;

	-- Юнит отступает, если выполнены ВСЕ нижеперечисленные условия:
	--    Ближний бой.
	--    Юнит проиграл бой или у атакующего есть способность страх или защищающийся сбежал с помощью способности fleet.
	--    Юнит является обороняющимся, т.е. не он инициировал атаку.
	--    Потери юнита за бой составили не менее XX% хитпойнтов юнита до боя или у атакующего есть статус fear или защищающийся сбежал с помощью способности fleet
	--    У юнита нет статуса "бесстрашный"
	local wasDefenderRetreat = false;

	if (battleInfo.battleType == CLOSE_COMBAT
    	and (victorySide ~= ROLE_DEFENDER or attacker:HasStatus("fear") or defenderEscaped)
    	and not defender:IsDisbanded() 
    	and defender:GetMovementType() ~= "Static"
    	and (lostDefender >= defenderStartHP * 0.50 or attacker:HasStatus("fear") or battleGlobal.alwaysRetreat or defenderEscaped)
    	and not defender:HasStatus("fearless"))
	then
	    -- отсупление!
       	wasDefenderRetreat = true; 
        report:NeedDefenderMove();
	end;

	-- выжил ли город после всего этого? и был ли мальчик?
	local hasDefenderCoverAlive = (battleInfo.defCover ~= nil and not battleInfo.defCover:IsDisbanded());

	-- Если рукопашная атака уничтожила юнит врага или заставила его отступить, то нападающий юнит 
	-- совершает автоматическое перемещение на его клетку (если там не осталось живого города)
	if (battleInfo.battleType == CLOSE_COMBAT
   		and not attacker:IsDisbanded() 
   		and not hasDefenderCoverAlive
    	and attacker:GetMovementType() ~= "Static"
   		and (defender:IsDisbanded() or wasDefenderRetreat))
	then
		report:NeedAttackerMove();
	end;

	LogPopTab();

	-- вывод результирующей информации
    LogOut(LEVEL_2, "");
    LogOut(LEVEL_2, "Attacker: " .. UnitEndInfo(attacker, lostAttacker));
    LogOut(LEVEL_2, "Defender: " .. UnitEndInfo(defender, lostDefender));

	if (battleInfo.defCover ~= nil)
	then
	    LogOut(LEVEL_2, "Cover: " .. UnitEndInfo(battleInfo.defCover, lostCover));
	end;

    if (wasDefenderRetreat)
    then
        LogOut(LEVEL_2, "Defender retreat!");
    end;

    LogOut(LEVEL_2, victorySide .. " wins!");

    LogOut(LEVEL_1, "<---- Battle: end");

	return 0;
end;




-----------------------------------------------------
-- игрок кастует Заклинание на юнит
-----------------------------------------------------
function MagicAttack(spell, defender, defCover, report)

    LogOut(LEVEL_1, "\n----> MagicAttack: begin...");

	-- вывод стартовой информации
    LogOut(LEVEL_2, "Spell: " .. tostring(spell));
    LogOut(LEVEL_2, "Defender: " .. UnitBeginInfo(defender));
    LogOut(LEVEL_2, "");

	LogPushTab();

    -- начало боя - настройка глобальных параметров
    battleInfo = MakeBattleInfo(MAGIC_ATTACK, spell, defender, defCover, true);

	-- начальное состояние
	local defenderStartHP = defender:GetAliveHP();
	local coverStartHP = 0;
	if (battleInfo.defCover ~= nil)
	then
		coverStartHP = battleInfo.defCover:GetAliveHP();
	end;

    -- считаем вероятность нанесения критикалов. критикалы действуют на все атаки
	CalculateCriticals(battleInfo, report);

    -- пока одна инициатива. например, 10я. потому что хорошее число.
	battleInfo.currentInitiative = 10;
	report:RegisterInitiative(battleInfo.currentInitiative);

	-- стоим в замке? он тоже получит свой паек на сегодня. причем сначала, чтобы защищающийся еще не ослабил атакующего
	local lostCover = 0;
	if (battleInfo.defCover ~= nil)
	then
		local attToCoverCombatants = battleInfo.unitCombatants[3];
		local attToCoverAction = attToCoverCombatants.attacker:GetCurrentAction();
		local attToCoverCanApplied = CanActionBeApplied(battleInfo, attToCoverAction, attToCoverCombatants, false);

		DoAttacks(battleInfo, attToCoverCombatants, report, attToCoverCanApplied);

		-- применяем полученные потери
		battleInfo.defCover:ApplyDamage(false);

		ApplyUseActions(battleInfo, attToCoverCombatants, attToCoverCanApplied);

		-- выявление победившего и наказание проигравшего
		local coverEndHP = defCover:GetAliveHP();
		lostCover = coverStartHP - coverEndHP;

	    -- в конце боя заполняем статистику
		report:SetBeforeHP(battleInfo.defCoverId, coverStartHP);
		report:SetLostHP(battleInfo.defCoverId, lostCover);
		report:SetDisbanded(battleInfo.defCoverId, battleInfo.defCover:IsDisbanded());
	end;

	-- применяем все атаки заклинаний
	local magicAttCombatants = battleInfo.unitCombatants[1];
	local magicAttAction = magicAttCombatants.attacker:GetCurrentAction();
	local magicAttCanApplied = CanActionBeApplied(battleInfo, magicAttAction, magicAttCombatants, false);

	DoAttacks(battleInfo, magicAttCombatants, report, magicAttCanApplied);

	-- применяем полученные потери
	battleInfo.defender:ApplyDamage(false);

	ApplyUseActions(battleInfo, magicAttCombatants, magicAttCanApplied);

	-- выявление победившего и наказание проигравшего
	local defenderEndHP = defender:GetAliveHP();
	local lostDefender = defenderStartHP - defenderEndHP;

    -- в конце боя заполняем статистику
    report:SetVictorySide(ROLE_ATTACKER);
	report:SetBattleType(battleInfo.battleType);

	report:SetBeforeHP(battleInfo.defenderId, defenderStartHP);
	report:SetLostHP(battleInfo.defenderId, lostDefender);
	report:SetDisbanded(battleInfo.defenderId, defender:IsDisbanded());

	LogPopTab();

	-- вывод результирующей информации
    LogOut(LEVEL_2, "");
    LogOut(LEVEL_2, "Defender: " .. UnitEndInfo(defender, lostDefender));

	if (battleInfo.defCover ~= nil)
	then
	    LogOut(LEVEL_2, "Cover: " .. UnitEndInfo(battleInfo.defCover, lostCover));
	end;

    LogOut(LEVEL_1, "<---- MagicAttack: end");

	return 0;
end;



-- проверка: можно ли попытаться применить данный экшен (резист будем проверять не здесь)
-- inFuture - можно ли в принципе будет применить экшен (используется для AI для оценки возможности боя)
function CanActionBeApplied(battleInfo, action, combatants, inFuture)

	-- если не прошел кулдаун - не применяем
    if (action:GetCooldown() > 0)
    then
		LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: cooldown > 0: " .. tostring(action:GetCooldown()));
		return false;
    end;

	-- боевые здания могут атаковать только 1 раз за ход
	if (battleInfo.attacker:GetMovementType() == "Static" and action:WasUsed())
	then
		LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: only 1 attack action per turn.");

		return false;
	end;

	-- боевые здания (зАмки) не уничтожаются до конца, но и не представляют угрозы
	if (combatants.defender:IsDisbanded() and combatants.defender:GetAliveHP() <= 0)
	then
		LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: can not attack target. Target has been disbanded.");

		return false;
	end;

    -- юнит, являющийся невидимым на данным момент атаковать невозможно никому, кроме юнитов с TrueSight
--[[if (not combatants.defender:IsVisibleFor(combatants.attacker:GetFraction()))
    then
		LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: can not attack target. Target is invisible.");
        return false;
    end;
]]--
    -- если инициатор боя - наземный юнит, а обороняется - летающий, и нападают не на город,
    -- то с обеих сторон не используются атаки Close Combat Only
    if (battleInfo.attacker:GetMovementType() ~= "Flyer" and battleInfo.defender:GetMovementType() == "Flyer"
        and action:IsCloseCombat() and battleInfo.defCover == nil)
    then
        LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: <ground -> flying> - ignore CloseCombat attacks");

        return false;
    end;

	------------------------------------------
	-- если у нас только проверка, то выходим, а иначе применяем по полной 
	------------------------------------------
	if (inFuture)
	then
	    -- все прочие атаки могут использоваться
    	LogOut(LEVEL_3, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " Can be used optionaly");
		return true;
	end;

	------------------------------------------
	-- проводим дополнительныве проверки
	------------------------------------------

--[[ ОРИГИНАЛЬНЫЙ ВАРИАНТ: ЕСЛИ НА СОСЕДНЕЙ КЛЕТКЕ ЕСТЬ ВРАГ, ТО ДИСТАНЦИОННЫЕ АТАКИ ПРИМЕНЯТЬ НЕЛЬЗЯ ВООБЩЕ
    -- если атака Ranged Only - то не работает, если на соседней клетке есть противник
    if (action:GetDamageType() == "RangedAttack")
    then
        -- сперва выполняем легкую проверку, а затем - тяжелую...
        if (battleInfo.battleType == CLOSE_COMBAT or g_world:UnitHasEnemyInArea(combatants.attacker, 1))
        then

            LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: cannot use range attack near enemy");

            return false;
        end;
    end;
]]--

--[[Временно отключаем, и тем самым возвращаем возможность стрелкам стрелять в любых врагов, даже если кто-то из врагов стоит на соседней клетке
    -- НОВЫЙ ВАРИАНТ:    
    -- если атака RangedCombat, а на соседней клетке враг - ее можно применять только по ближним врагам, 
    -- причем с пенальтей (пенальти начисляется в другом месте)
    if (action:GetDamageType() == "RangedAttack")
    then
        if (battleInfo.battleType ~= CLOSE_COMBAT and g_world:UnitHasEnemyInArea(combatants.attacker, 1))
        then

            LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: cannot use range attack when enemy is near");

            return false;
        end;
    end;
]]--

--[[ Мы снова разрешаем использовать стрелковую атаку в обороне. В другом месте мы внесем пенальти.
    -- ЗАПРЕТ НА ИСПОЛЬЗОВАНИЕ СТРЕЛКОВЫХ АТАК В ОБОРОНЕ
    if (attack:GetUsageMode() == "RangedCombat" and combatants.attacker:GetRole() == ROLE_DEFENDER)
    then
        LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: cannot shoot in defence");

        return false;
    end;
]]--

    -- если цель юнита находится дальше действия атаки - такая атака использоваться не будет
    if (action:GetRange() < battleInfo.battleRange) 
    then
        LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: out of range (" .. action:GetRange() .. "<" .. battleInfo.battleRange .. ")");

        return false;
    end;

    -- если мы атакованы дистанционной атакой, не используем CloseCombat атаки в ответ
	if (battleInfo.battleType == RANGED_COMBAT and action:IsCloseCombat())
	then
       	LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: rangedCombat: cannot defend with melee attack!");
        return false;
	end;

    -- LOS - если юнит не видит противника из-за ландшафта, то он не может использовать атаки
    -- определяем, загораживается ли защищающийся юнит холмом (летуны, гиганты и юниты, стоящие на холме не загораживаются)
    --[[
    
    ВРЕМЕННО ОТКЛЮЧЕНО ИСПОЛЬЗОВАНИЕ ЛИНИИ ВИДИМОСТИ
        
    local IsHiddenByHills = true;
    if (g_world:GetLandType(battleInfo.defender:GetPosition()) == "Hills" and
            g_world:GetLandType(battleInfo.attacker:GetPosition()) == "Hills")
    then
        IsHiddenByHills = false;
    end;
    if (battleInfo.defender:GetMovementType() == "Flyer")
    then
        IsHiddenByHills = false;
    end;
    

    -- если дистанция атаки <= 1, то можем атаковать без учета LOS
    if (action:IsRangedCombat())
    then
        -- находим список клеток, лежащих на линии огня
        local los = g_world:GetLineOfSight(battleInfo.attacker, battleInfo.defender);

        LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: starting calculate LOS with " .. los:GetSize() .. "size.");

        for index = 0, los:GetSize() - 1, 1 do
            -- для каждой клетки определяем, загораживает ли она линию огня
            local pos = los:GetTile(index);
            if (g_world:GetLandType(pos) == "Forest" or g_world:GetLandType(pos) == "ForestHills")
            then
                LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: can not see the target. Forest on LOS.");
                return false;
            end;
            if ((g_world:GetLandType(pos) == "Hills" or g_world:GetLandType(pos) == "ForestHills") and
                IsHiddenByHills)
            then
                LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: can not see the target. Hills on LOS.");

                return false;
            end;
        end;
    end;
    ]]

    -- юнит, не имеющий ИстинногоЗрения не может атаковать дистанционной атакой невидимого юнита
 
     -- защищающийся может отвечать только если мы стоим на соседних клетках
    if (combatants.attacker:GetRole() == ROLE_DEFENDER and battleInfo.battleRange > 1) 
    then
        LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: defender cannot fight back - too far");

        return false;
    end;

	-- на стрелковую атаку теперь не отвечает никто
    if (combatants.attacker:GetRole() == ROLE_DEFENDER and battleInfo.missileAttack)
	then
        LogOut(LEVEL_2, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " OFF: missile attack, defender cannot fight back");

		return false;
	end;

    -- все прочие атаки могут использоваться
    LogOut(LEVEL_3, combatants.attacker:GetRole() .. ": " .. tostring(action) .. " USED");

    return true;
end;



-----------------------------------------------------
-- можем ли мы атаковать другой юнит
-----------------------------------------------------
-- inFuture - можно ли в принципе будет применить экшен (используется для AI для оценки возможности боя)
function CanAttackUnit(attacker, defender, defCover, actionName, inFuture)

    LogOut(LEVEL_1, "\n----> CanAttackUnit: " .. tostring(attacker) .. " -> " .. tostring(defender) .. ", " .. tostring(actionName));

	local result = true;

	LogPushTab();

	-- Атаковать можем только действующим юнитом или неразрушенным боевым зданием
	if (result and attacker:GetAliveHP() <= 0)
	then
        LogOut(LEVEL_2, "no hit points!");
    	result = false; 
	end;

	-- Атаковать можем только если есть для этого очки движения (города многут атаковать всегда)
   	
	if (result and attacker:GetMovementType() ~= "Static" and attacker:GetMovePoints() <= 0.0) 
	then 
        LogOut(LEVEL_2, "no move points!");
    	result = false; 
    end;

	-- На этом "уровне логики" атаковать можем только врагов (раньше надо было портить отношения, в стратегии!)
	if (result and g_world:GetUnitsRelation(attacker, defender) ~= "War") 
	then 
        LogOut(LEVEL_2, "cannot attack friends!");
    	result = false; 
    end;

    -- далее нужен тип боя - формируем структуру
	if (result)
	then
        battleInfo = MakeBattleInfo(actionName, attacker, defender, defCover, false);
    end;

	-- В рукопашную атаковать можем только проходимые хексы
	if (result and battleInfo.battleType == CLOSE_COMBAT and not g_world:CheckTerrainPassability(attacker, defender:GetPosition()))
	then 
        LogOut(LEVEL_2, "cannot attack impassable terrain!");
    	result = false; 
    end;

    -- проверяем указанный экшен
	if (result)
	then
		local action = attacker:GetCurrentAction();
		result = CanActionBeApplied(battleInfo, action, battleInfo.unitCombatants[1], inFuture);
	end;

	LogPopTab();

    LogOut(LEVEL_1, "<---- CanAttackUnit: result = " .. tostring(result));

	return result;
end;
