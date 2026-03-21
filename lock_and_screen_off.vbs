Option Explicit

' This script creates a "pseudo black screen":
' 1) lock the current Windows session
' 2) turn off the display without putting the PC to sleep
'
' Notes:
' - The PC must still be configured not to sleep.
' - If you want tasks to keep running with the lid closed, Windows power
'   settings must be set so closing the lid does nothing.

Dim shell
Dim ps

Set shell = CreateObject("WScript.Shell")

' Lock first so wake-up returns to the lock screen.
shell.Run "rundll32.exe user32.dll,LockWorkStation", 0, False

' Give Windows a moment to switch to the lock screen.
WScript.Sleep 1500

ps = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -EncodedCommand " & _
     "QQBkAGQALQBUAHkAcABlACAALQBUAHkAcABlAEQAZQBmAGkAbgBpAHQAaQBvAG4AIAAnAHUAcwBpAG4AZwAgAFMAeQBzAHQAZQBtADsAdQBzAGkAbgBnACAAUwB5AHMAdABlAG0ALgBSAHUAbgB0AGkAbQBlAC4ASQBuAHQAZQByAG8AcABTAGUAcgB2AGkAYwBlAHMAOwBwAHUAYgBsAGkAYwAgAHMAdABhAHQAaQBjACAAYwBsAGEAcwBzACAATgBhAHQAaQB2AGUATQBlAHQAaABvAGQAcwB7AFsARABsAGwASQBtAHAAbwByAHQAKAAiACIAdQBzAGUAcgAzADIALgBkAGwAbAAiACIAKQBdACAAcAB1AGIAbABpAGMAIABzAHQAYQB0AGkAYwAgAGUAeAB0AGUAcgBuACAASQBuAHQAUAB0AHIAIABTAGUAbgBkAE0AZQBzAHMAYQBnAGUAKABJAG4AdABQAHQAcgAgAGgAVwBuAGQALABpAG4AdAAgAE0AcwBnACwASQBuAHQAUAB0AHIAIAB3AFAAYQByAGEAbQAsAEkAbgB0AFAAdAByACAAbABQAGEAcgBhAG0AKQA7AH0AJwAKAFsAdgBvAGkAZABdAFsATgBhAHQAaQB2AGUATQBlAHQAaABvAGQAcwBdADoAOgBTAGUAbgBkAE0AZQBzAHMAYQBnAGUAKABbAEkAbgB0AFAAdAByAF0AMAB4AEYARgBGAEYALAAwAHgAMAAxADEAMgAsAFsASQBuAHQAUAB0AHIAXQAwAHgARgAxADcAMAAsAFsASQBuAHQAUAB0AHIAXQAyACkA"

' Send the "power off monitor" message. Running it twice is a little more
' reliable on some lock-screen / multi-monitor setups.
shell.Run ps, 0, False
WScript.Sleep 400
shell.Run ps, 0, False

Set shell = Nothing
