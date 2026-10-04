--[[-------------------------------------------------
    Здесь находятся функции, используемые генератором
    логической карты
-------------------------------------------------]]--

-- размер ушей в хексах для всех стратегических карт
MAP_BORDER_SIZE_STRATEGIC = 4;


function FillBasicContentParams(noiseFrequency, content)

	-- Радиус "континентальности".
	-- Чем больше радиус, тем больший участок суши необходимо будет найти для расположения города
	-- Для поиска места для столицы ищется участок ы указанном радиусе, полностью заполненный сушей
	-- Для поиска места для нейтрального города ищется участок, заполненный сушей минимум на 75%
	-- Для поиска места для локации или нода ищется участок, заполненный сушей минимум наполовину
    content.continentAccumRadius = 2 + noiseFrequency;
    -- минимальное расстояние между столицами
    content.interCapitalDistance = 6 + 0.5 * noiseFrequency;
    -- минимальное расстояние столицы от границ карты
	content.capitalBoundariesDistance = 3;
	-- минимальная "континентальность" (количество тайлов суши, пригодных для строительства) столиц
	content.capitalContinentarity = 37; -- 1 + 6 + 12 + 18
	-- зона нулевого поколения вокруг города
	content.capitalDeadZone = 3;

	-- минимальное поколение при генерации
    content.minStage = 1;
    content.maxStage = 3;
    -- расстояния между поколениями
    content.interStageDistance = 2 * noiseFrequency;
    content.interStageMinDistance = 1.5 * noiseFrequency;

    --распределяем нейтральные города по поколениям
    -- для каждого поколения задаем плотность городов (городов на хекс, например 0.05 - это 5 городов на 100 хексов)
	content.neutrals:clear();
    content.neutrals:add(0.00);      	-- поколение 0
    content.neutrals:add(0.02);		-- поколение 1
    content.neutrals:add(0.015);	-- поколение 2
    content.neutrals:add(0.01);		-- поколение 3
    content.neutrals:add(0.01);		-- поколение 4
    
    --распределяем локации по поколениям
    -- для каждого поколения задаем плотность локаций
    content.locs:clear();
    content.locs:add(0);				-- поколение 0
    content.locs:add(0.07);				-- поколение 1
    content.locs:add(0.10);				-- поколение 2
    content.locs:add(0.09);				-- поколение 3
    content.locs:add(0.01);				-- поколение 4

    --распределяем локальные ресурсы по поколениям
    -- для каждого поколения задаем плотность локальных ресурсов
    content.resources:clear();
    content.resources:add(0.07);				-- поколение 0
    content.resources:add(0.11);				-- поколение 1
    content.resources:add(0.13);				-- поколение 2
    content.resources:add(0.15);				-- поколение 3
    content.resources:add(0.10);				-- поколение 4

    content.interTownDistance = 3 + noiseFrequency;		-- минимальное расстояние между нейтральными городами
    content.interLocationDistance = 2 + noiseFrequency;	-- минимальное расстояние между локациями и нодами
    content.locTownDistance = 2 + noiseFrequency; 			-- минимальное расстояние между локациями и городами
	content.interLocTypesDistance = 4;					-- минимальное расстояние между одинаковыми типами локаций
	content.interResourceDistance = 2;					-- минимальное расстояние между локальными ресурсами
	content.nearWatersideDistance = 2;		-- Максимальное расстояние до берега (в море), при котором поколение считается первым					-- минимальное расстояние между локальными ресурсами

    --распределяем морские логова по поколениям
    -- для каждого поколения задаем плотность локальных ресурсов
    content.waterLocs:clear();
    content.waterLocs:add(0.04);			-- поколение 1
    content.waterLocs:add(0.05);			-- поколение 2

    content.interWaterLocsDistance = 2;			-- минимальное расстояние между морскими логовами
 

	content.townContinentarity = 19;
	content.locationContinentarity = 7;

	content.townBoundariesDistance = 2;
	content.locationBoundariesDistance = 1;
end;

function PatchIslandsContentParams(content)
    -- минимальное расстояние между столицами
    content.interCapitalDistance = 4;
	-- минимальная "континентальность" (количество тайлов суши, пригодных для строительства) столиц
	content.capitalContinentarity = 19; -- 1 + 6 + 12

	content.townContinentarity = 7;
end;


function FillFragmentContentParams(noiseFrequency, content)

	-- Радиус "континентальности".
	-- Чем больше радиус, тем больший участок суши необходимо будет найти для расположения города
	-- Для поиска места для столицы ищется участок ы указанном радиусе, полностью заполненный сушей
	-- Для поиска места для нейтрального города ищется участок, заполненный сушей минимум на 75%
	-- Для поиска места для локации или нода ищется участок, заполненный сушей минимум наполовину
    content.continentAccumRadius = 2;
    -- минимальное расстояние между столицами
    content.interCapitalDistance = 30;
    -- минимальное расстояние столицы от границ карты
	content.capitalBoundariesDistance = 3;
	-- минимальная "континентальность" (количество тайлов суши, пригодных для строительства) столиц
	content.capitalContinentarity = 1; -- 1 + 6 + 12 + 18


	-- минимальное поколение при генерации
    content.minStage = 3;
    content.maxStage = 5;
    -- расстояния между поколениями
    content.interStageDistance = 4 * noiseFrequency;
    content.interStageMinDistance = 1.8 * noiseFrequency;

    --распределяем нейтральные города по поколениям
    -- для каждого поколения задаем плотность городов (городов на хекс, например 0.05 - это 5 городов на 100 хексов)
	content.neutrals:clear();
--[[    content.neutrals:add(0.01);     -- поколение 0
    content.neutrals:add(0.02);		-- поколение 1
    content.neutrals:add(0.02);		-- поколение 2
    content.neutrals:add(0.02);		-- поколение 3
    content.neutrals:add(0.02);		-- поколение 4
--]]    

    --распределяем локации по поколениям
    -- для каждого поколения задаем количество локаций
    content.locs:clear();
    content.locs:add(0);				-- поколение 0
    content.locs:add(0);				-- поколение 1
    content.locs:add(0);				-- поколение 2
    content.locs:add(0.09);				-- поколение 3
    content.locs:add(0.09);				-- поколение 4
    content.locs:add(0.05);				-- поколение 5

    --распределяем локальные ресурсы по поколениям
    -- для каждого поколения задаем количество локальных ресурсов
    content.resources:clear();
    content.resources:add(0);				-- поколение 0
    content.resources:add(0);				-- поколение 1
    content.resources:add(0);				-- поколение 2
    content.resources:add(0.14);			-- поколение 3
    content.resources:add(0.15);			-- поколение 4

    content.interTownDistance = 4;		-- минимальное расстояние между нейтральными городами
    content.interLocationDistance = 3;	-- минимальное расстояние между локациями и нодами
    content.locTownDistance = 3; 			-- минимальное расстояние между локациями и городами
	content.interLocTypesDistance = 4;					-- минимальное расстояние между одинаковыми типами локаций
	content.interResourceDistance = 2;					-- минимальное расстояние между локальными ресурсами
	content.nearWatersideDistance = 1;		-- Максимальное расстояние до берега (в море), при котором поколение считается первым					-- минимальное расстояние между локальными ресурсами

    --распределяем морские логова по поколениям
    -- для каждого поколения задаем плотность локальных ресурсов
    content.waterLocs:clear();
    content.waterLocs:add(0.1);				-- поколение 1
    content.waterLocs:add(0.15);			-- поколение 2

    content.interWaterLocsDistance = 2;			-- минимальное расстояние между морскими логовами

	content.townContinentarity = 19;
	content.locationContinentarity = 7;

	content.townBoundariesDistance = 1;
	content.locationBoundariesDistance = 1;
end;

function FillPlanarLakes(result)
	-- границы карты
    result.borderSize = IPoint2(MAP_BORDER_SIZE_STRATEGIC, MAP_BORDER_SIZE_STRATEGIC);
    -- тип карты
    result.mapType = "Planar"; -- Cylindrical or Planar
    -- количество воды на карте
    result.minSeaPercent = 0; -- 0 .. 1
    result.maxSeaPercent = 0.2; -- 0 .. 1
    --  количество межхексовых путей рек 
	-- Реки временно отключены!!!
    result.totalRiverLength = 0; -- 50 * result.noiseFrequency; -- 0 .. 
    -- максимальная величина, на которую река может течь вверх. чем больше величина, тем более закрученные реки
	result.riverUpError = 0.005;
	result.riverDownError = 0.005;
	result.riverStraightCoef = 1.1;
	result.minRiverStartElevation = 0.4;
	result.maxRiverEndElevation = -0.01;
	
	-- пресеты для генерации карты высот находятся в Data\GameData\Landscape\HeightGenPresets
	-- Убираем у файла расширение - получаем имя пресета
	result.heightGenPreset = "lakes"; 
	result.tempGenPreset = "temperature_plane_main";
	result.humidGenPreset = "humidity_plane_tiny";
end;

function FillPlanarPangeya(result)
	-- границы карты
    result.borderSize = IPoint2(MAP_BORDER_SIZE_STRATEGIC, MAP_BORDER_SIZE_STRATEGIC);
    -- тип карты
    result.mapType = "Planar"; -- Cylindrical or Planar
    -- количество воды на карте
    result.minSeaPercent = 0.1; -- 0 .. 1
    result.maxSeaPercent = 0.7; -- 0 .. 1
    --  количество межхексовых путей рек 
	-- Реки временно отключены!!!
    result.totalRiverLength = 0; -- 50 * result.noiseFrequency; -- 0 .. 
    -- максимальная величина, на которую река может течь вверх. чем больше величина, тем более закрученные реки
	result.riverUpError = 0.005;
	result.riverDownError = 0.005;
	result.riverStraightCoef = 1.1;
	result.minRiverStartElevation = 0.4;
	result.maxRiverEndElevation = -0.01;
	
	-- пресеты для генерации карты высот находятся в Data\GameData\Landscape\HeightGenPresets
	-- Убираем у файла расширение - получаем имя пресета
	result.heightGenPreset = "pangeya"; 
	result.tempGenPreset = "temperature_plane_main";
	result.humidGenPreset = "humidity_plane_tiny";
end;

function FillPlanarContinents(result)
	-- границы карты
    result.borderSize = IPoint2(MAP_BORDER_SIZE_STRATEGIC, MAP_BORDER_SIZE_STRATEGIC);
    -- тип карты
    result.mapType = "Planar"; -- Cylindrical or Planar
    -- количество воды на карте
    result.minSeaPercent = 0.4; -- 0 .. 1
    result.maxSeaPercent = 0.6; -- 0 .. 1
    --  количество межхексовых путей рек 
	-- Реки временно отключены!!!
    result.totalRiverLength = 0; -- 50 * result.noiseFrequency; -- 0 .. 
    -- максимальная величина, на которую река может течь вверх. чем больше величина, тем более закрученные реки
	result.riverUpError = 0.005;
	result.riverDownError = 0.005;
	result.riverStraightCoef = 1.1;
	result.minRiverStartElevation = 0.4;
	result.maxRiverEndElevation = -0.01;
	
	-- пресеты для генерации карты высот находятся в Data\GameData\Landscape\HeightGenPresets
	-- Убираем у файла расширение - получаем имя пресета
	result.heightGenPreset = "continents"; 
	result.tempGenPreset = "temperature_plane_main";
	result.humidGenPreset = "humidity_plane_tiny";
end;

function FillPlanarIslands(result)
	-- границы карты
    result.borderSize = IPoint2(MAP_BORDER_SIZE_STRATEGIC, MAP_BORDER_SIZE_STRATEGIC);
    -- тип карты
    result.mapType = "Planar"; -- Cylindrical or Planar
    -- количество воды на карте
    result.minSeaPercent = 0.5; -- 0 .. 1
    result.maxSeaPercent = 0.7; -- 0 .. 1
    --  количество межхексовых путей рек 
	-- Реки временно отключены!!!
    result.totalRiverLength = 0; -- 50 * result.noiseFrequency; -- 0 .. 
    -- максимальная величина, на которую река может течь вверх. чем больше величина, тем более закрученные реки
	result.riverUpError = 0.005;
	result.riverDownError = 0.005;
	result.riverStraightCoef = 1.1;
	result.minRiverStartElevation = 0.4;
	result.maxRiverEndElevation = -0.01;
	
	-- пресеты для генерации карты высот находятся в Data\GameData\Landscape\HeightGenPresets
	-- Убираем у файла расширение - получаем имя пресета
	result.heightGenPreset = "islands"; 
	result.tempGenPreset = "temperature_plane_main";
	result.humidGenPreset = "humidity_plane_tiny";
end;

function FillCylinderLakes(result)
	-- границы карты
    result.borderSize = IPoint2(0, MAP_BORDER_SIZE_STRATEGIC);
    -- тип карты
    result.mapType = "Cylindrical"; -- Cylindrical or Planar
    -- количество воды на карте
    result.minSeaPercent = 0.1; -- 0 .. 1
    result.maxSeaPercent = 0.2; -- 0 .. 1
    --  количество межхексовых путей рек
    result.totalRiverLength = 50 * result.noiseFrequency; -- 0 .. 
    -- максимальная величина, на которую река может течь вверх. чем больше величина, тем более закрученные реки
	result.riverUpError = 0.004;
	result.riverDownError = 0.004;
	result.riverStraightCoef = 1.05;

	-- пресеты для генерации карты высот находятся в Data\GameData\Landscape\HeightGenPresets
	-- Убираем у файла расширение - получаем имя пресета
	result.heightGenPreset = "lakes"; 
	result.tempGenPreset = "temperature_cylinder";
	result.humidGenPreset = "humidity_cylinder";
end;

function FillCylinderPangeya(result)
	-- границы карты
    result.borderSize = IPoint2(0, MAP_BORDER_SIZE_STRATEGIC);
    -- тип карты
    result.mapType = "Cylindrical"; -- Cylindrical or Planar
    -- количество воды на карте
    result.minSeaPercent = 0.1; -- 0 .. 1
    result.maxSeaPercent = 0.7; -- 0 .. 1
    --  количество межхексовых путей рек 
	-- Реки временно отключены!!!
    result.totalRiverLength = 0; -- 50 * result.noiseFrequency; -- 0 .. 
    -- максимальная величина, на которую река может течь вверх. чем больше величина, тем более закрученные реки
	result.riverUpError = 0.005;
	result.riverDownError = 0.005;
	result.riverStraightCoef = 1.1;
	result.minRiverStartElevation = 0.4;
	result.maxRiverEndElevation = -0.01;
	
	-- пресеты для генерации карты высот находятся в Data\GameData\Landscape\HeightGenPresets
	-- Убираем у файла расширение - получаем имя пресета
	result.heightGenPreset = "pangeya_cylinder"; 
	result.tempGenPreset = "temperature_cylinder";
	result.humidGenPreset = "humidity_cylinder";
end;

function FillCylinderContinents(result)
	-- границы карты
    result.borderSize = IPoint2(0, MAP_BORDER_SIZE_STRATEGIC);
    -- тип карты
    result.mapType = "Cylindrical"; -- Cylindrical or Planar
    -- количество воды на карте
    result.minSeaPercent = 0.4; -- 0 .. 1
    result.maxSeaPercent = 0.6; -- 0 .. 1
    --  количество межхексовых путей рек
    result.totalRiverLength = 50 * result.noiseFrequency; -- 0 .. 
    -- максимальная величина, на которую река может течь вверх. чем больше величина, тем более закрученные реки
	result.riverUpError = 0.004;
	result.riverDownError = 0.004;
	result.riverStraightCoef = 1.05;

	-- пресеты для генерации карты высот находятся в Data\GameData\Landscape\HeightGenPresets
	-- Убираем у файла расширение - получаем имя пресета
	result.heightGenPreset = "continents_cylinder"; 
	result.tempGenPreset = "temperature_cylinder";
	result.humidGenPreset = "humidity_cylinder";
end;

function FillCylinderIslands(result)
	-- границы карты
    result.borderSize = IPoint2(0, MAP_BORDER_SIZE_STRATEGIC);
    -- тип карты
    result.mapType = "Cylindrical"; -- Cylindrical or Planar
    -- количество воды на карте
    result.minSeaPercent = 0.5; -- 0 .. 1
    result.maxSeaPercent = 0.7; -- 0 .. 1
    --  количество межхексовых путей рек
    result.totalRiverLength = 50 * result.noiseFrequency; -- 0 .. 
    -- максимальная величина, на которую река может течь вверх. чем больше величина, тем более закрученные реки
	result.riverUpError = 0.004;
	result.riverDownError = 0.004;
	result.riverStraightCoef = 1.05;

	-- пресеты для генерации карты высот находятся в Data\GameData\Landscape\HeightGenPresets
	-- Убираем у файла расширение - получаем имя пресета
	result.heightGenPreset = "islands_cylinder"; 
	result.tempGenPreset = "temperature_cylinder";
	result.humidGenPreset = "humidity_cylinder";
end;
-- получить из пользовательских параметров системные
function ConvertStrategicParams(worldType, userParams, result)

	-- настраиваем размеры
	if (userParams.size == "Tiny")
	then
		result.gameAreaSize = IPoint2(16, 16); --256
		result.noiseFrequency = 1;
		result.evilLocks = 4;

	elseif (userParams.size == "Small")
	then
		result.gameAreaSize = IPoint2(28, 20); --560
		result.noiseFrequency = 1.5;
		result.evilLocks = 6;

	elseif (userParams.size == "Normal")
	then
		result.gameAreaSize = IPoint2(44, 28); --1232
		result.noiseFrequency = 2;
		result.evilLocks = 7;

	elseif (userParams.size == "Large")
	then
		result.gameAreaSize = IPoint2(64, 32); --2048
		result.noiseFrequency = 3;
		result.evilLocks = 8;

	elseif (userParams.size == "Huge")
	then
		result.gameAreaSize = IPoint2(80, 40); --3200
		result.noiseFrequency = 4;
		result.evilLocks = 10;

	else
        SystemErrOut("\nINVALID PARAMETER: size='" .. userParams.size .. "'\n");
	end;

	-- заполняем параметры
	if (userParams.mapType == "Planar")
	then
		if (userParams.water == "Lakes")
		then
			-- моря и озёра. потом разделим
			FillPlanarLakes(result);
		elseif (userParams.water == "Pangeya")
		then
			-- континенты
			FillPlanarPangeya(result);
		elseif (userParams.water == "Continents")
		then
			-- континенты
			FillPlanarContinents(result);
		else
			-- острова
			FillPlanarIslands(result);
		end;

	elseif (userParams.mapType == "Cylindrical")
	then
		if (userParams.water == "Lakes")
		then
			-- моря и озёра. потом разделим
			FillCylinderLakes(result);
		elseif (userParams.water == "Pangeya")
		then
			-- континенты
			FillCylinderPangeya(result);
		elseif (userParams.water == "Continents")
		then
			-- континенты
			FillCylinderContinents(result);
		else
			-- острова
			FillCylinderIslands(result);
		end;

	else
        SystemErrOut("\nINVALID PARAMETER: mapType='" .. userParams.mapType .. "'\n");
		return;
	end;

	-- добавляем кляксы на ландшафт
	result:clearPatches();
	result:addPatch("lava_small");

	-- параметры генерации контента
	FillBasicContentParams(result.noiseFrequency, result.content);

	if (userParams.water == "Islands")
	then
		PatchIslandsContentParams(result.content);
	end;
end;


function ConvertFragmentParams(result)

	-- настраиваем размеры
	result.gameAreaSize = IPoint2(16, 16);
	result.noiseFrequency = 1;

	FillPlanarLakes(result);
    result.borderSize = IPoint2(4, 4);

	-- добавляем кляксы на ландшафт
	result:clearPatches();

	-- в карманы тоже можно добавлять кляксы
	-- например, так:
	-- if (result.preset == "Lava")
	-- then
	--	result:addPatch("lava_small");
	-- end;
    
	-- параметры генерации контента
	FillFragmentContentParams(result.noiseFrequency, result.content);
end;
