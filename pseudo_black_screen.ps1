# Locks Windows and keeps the display effectively off without putting the PC
# to sleep.
#
# Why the extra loop:
# Some Windows lock-screen events or notifications can wake the display a short
# time after it has been turned off. To make the behavior stable, this script
# keeps sending the "monitor off" signal until actual user input is detected.
# Once you move the mouse or press a key, the script exits and lets the screen
# wake normally so you can unlock the machine.

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class NativeMethods
{
    [DllImport("user32.dll")]
    public static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);

    [StructLayout(LayoutKind.Sequential)]
    public struct LASTINPUTINFO
    {
        public uint cbSize;
        public uint dwTime;
    }
}
"@

function Turn-OffDisplay {
    # SC_MONITORPOWER / power off monitor
    [void][NativeMethods]::SendMessage([IntPtr]0xFFFF, 0x0112, [IntPtr]0xF170, [IntPtr]2)
}

function Get-LastInputTick {
    $info = New-Object NativeMethods+LASTINPUTINFO
    $info.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf([type][NativeMethods+LASTINPUTINFO])
    [void][NativeMethods]::GetLastInputInfo([ref]$info)
    return [uint32]$info.dwTime
}

$maxKeepOffSeconds = 43200
$pollSeconds = 5

# Lock first so any wake-up returns to the lock screen.
Start-Process -FilePath "rundll32.exe" -ArgumentList "user32.dll,LockWorkStation" -WindowStyle Hidden

# Give Windows a moment to switch into the locked session.
Start-Sleep -Milliseconds 1500

$baselineInputTick = Get-LastInputTick

# Send twice for better reliability on some systems.
Turn-OffDisplay
Start-Sleep -Milliseconds 400
Turn-OffDisplay

$deadline = (Get-Date).AddSeconds($maxKeepOffSeconds)

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds $pollSeconds

    $currentInputTick = Get-LastInputTick
    if ($currentInputTick -ne $baselineInputTick) {
        break
    }

    Turn-OffDisplay
}
