--[[-------------------------------------------------
    Здесь находятся вспомогательные функции для работы
    со скриптами
-------------------------------------------------]]--

-----------------------------------------------------
-- сформировать состояние юнита для вывода в лог
-----------------------------------------------------
function UnitBeginInfo(unit)

    local infoString = tostring(unit) .. " hp=" .. unit:GetAliveHP() .. "/" .. unit:GetTotalHP();
    return infoString;
end;


-----------------------------------------------------
-- сформировать состояние юнита на конец для вывода в лог
-----------------------------------------------------
function UnitEndInfo(unit, delta)

    local infoString = tostring(unit) .. " hp=" .. unit:GetAliveHP() .. "/" .. unit:GetTotalHP();

    if (delta > 0)
    then
        infoString = infoString .. " (-" .. delta .. ")"
    else
        infoString = infoString .. " (0)"
    end;

    return infoString;
end;