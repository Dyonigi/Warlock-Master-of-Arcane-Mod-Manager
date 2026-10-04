--[[-------------------------------------------------
полезные функции дл€ расчЄтов в »»
-------------------------------------------------]]--

-- поиск наилучшей позиции дл€ атаки
-- возвращает индекс в массиве
function findBestPositionToAttack(attacker, target, actionName, positions, adjacentEnemyK, adjacentAllyK, report)

    LogOut(LEVEL_4, "\n----> findBestPositionToAttack: begin...");

	local startPos = attacker:GetPosition();
	local result = 0;
	local bestTerrainK = 0;
	local bestRange = 0;

    -- начало бо€ - настройка глобальных параметров
    -- важно! без учета защиты от города. если надо учесть - передавать сюда вместо nil
    local battleInfo = MakeBattleInfo(actionName, attacker, target, nil, nil, true);

    -- пока одна инициатива. например, 10€. потому что хорошее число.
	battleInfo.currentInitiative = 10;

	LogPushTab();

	for cellIdx = 0, positions:size() - 1, 1 do
		-- получаем юнита в точке

		local cell = positions:at(cellIdx);

		attacker:TeleportTo(cell);

		local terrainK = CalculateTerrainK(battleInfo, battleInfo.unitCombatants[1], report);

	    LogOut(LEVEL_4, "\n----> K("..cell.pos.x..","..cell.pos.y..","..cell.worldID..")="..terrainK);

	    -- провер€ем врагов вокруг €чейки
	    if (g_world:hasAdjacentEnemies(attacker, cell))
	    then
	    	terrainK = terrainK * adjacentEnemyK;
	    end;

	    -- провер€ем друзей вокруг €чейки
	    if (g_world:hasAdjacentAllies(attacker, cell))
	    then
	    	terrainK = terrainK * adjacentAllyK;
	    end;

    	local range = g_world:calcDistance(startPos, cell);

		if ( terrainK > bestTerrainK  or (terrainK == bestTerrainK and bestRange > range) )
		then
    	    result = cellIdx;
    	    bestTerrainK = terrainK;
    	    bestRange = range;
		end;

	end;
	    
	LogPopTab();
    LogOut(LEVEL_4, "\n----> findBestPositionToAttack: end with result="..result);

	return result;
end;
