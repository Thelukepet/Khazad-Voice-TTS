import "Turbine.Gameplay"

local player = Turbine.Gameplay.LocalPlayer.GetInstance()

player.TargetChanged = function(sender, this)
    local target = sender:GetTarget()
    if target ~= nil then
        targetName = target:GetName() or "Target name not found"
    end
    
    -- gets logged in documents\The Lord of the Rings Online\script.log
    Turbine.Engine.ScriptLog(targetName)

    -- Prints to the in game chat if uncommented
    -- Turbine.Shell.WriteLine(targetName)
end