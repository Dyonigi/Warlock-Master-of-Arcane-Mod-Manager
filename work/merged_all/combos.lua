--[[

Здесь мы пишем комбы заклинаний

]]--


function comboLightning(defender)

    LogOut(LEVEL_1, "\n----> Combo lightning: begin...");
    local result = 0;

    -- проверяем статус
    if (defender:HasStatus("armored"))
    then
	    LogOut(LEVEL_2, "\n\tdefender has 'Armored' status. activating combo...");

	    local cells = g_world:getCellsInRadius(defender:GetPosition(), 2);

	    --вызываем комбу для всех юнитов в радиусе 2
		for cellIdx = 0, cells:size() - 1, 1 do
			-- получаем юнита в точке
			LogOut(LEVEL_2, "\n\tgetting cell at "..cellIdx);

			local cell = cells:at(cellIdx);

			LogOut(LEVEL_2, "\n\tcell at "..cellIdx.." is ["..cell.pos.x..","..cell.pos.y..","..cell.worldID.."]");

		    comboLightningChain(cell);
		end;

		result = 1;
    end;

    LogOut(LEVEL_1, "\n----> Combo lightning: end with result="..result);
	return result;
end;


function comboLightningChain(cell)

    LogOut(LEVEL_1, "\n----> Combo lightning chain: begin...");

    local defender = g_world:getUnitAt(cell);
    
    -- проверяем статус
    if (defender ~= nil and defender:HasStatus("armored"))
    then
    	--дамажим
	    LogOut(LEVEL_2, "\n\tdefender has 'Armored' status. applying damage...");

    end;
    
    LogOut(LEVEL_1, "\n----> Combo lightning chain: end.");
	return 0;
end;
