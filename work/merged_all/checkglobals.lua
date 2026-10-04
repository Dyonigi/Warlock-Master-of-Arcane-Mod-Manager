-- проверка на то, чтобы отлавливались очепятки. Тперь все глобальные переменные нужно задавать явно.

__checkGlobals = true

__declaredVariableNames = {}
setmetatable(_G, 
{
  __newindex = function (t, n, v)
    -- this function called only when user assign value to 
    -- global non-existing or 'nil-value' variable 
    __declaredVariableNames[n] = true
    rawset(t, n, v)
  end,

  __index = function (t, n)
    -- this function called only when user try to get (or indexing)
    -- global non-existing or 'nil-value' variable value

    if rawget(_G, "__checkGlobals") and not __declaredVariableNames[n] then
      error("attempt to read undeclared var '"..n.."'", 2)
    else
      return rawget(t, n)
    end
  end,
})