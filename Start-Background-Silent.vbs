' ============================================================================
' الباحث الحديثي — اردو، عربی (Zero-Window Silent Background Server Launcher)
' Runs `localhost:8088` and `localhost:8080` silently in the background via
' `pythonw.exe` with ZERO console window, so `http://localhost:8088` is always live!
' ============================================================================
Option Explicit

Dim fso, shell, appDir, pyw, py, scriptPath
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
If fso.FolderExists("D:\علمی معاون پرجیکٹ\حدیث سرچ\.venv") Then
    appDir = "D:\علمی معاون پرجیکٹ\حدیث سرچ"
End If

shell.CurrentDirectory = appDir
pyw = appDir & "\.venv\Scripts\pythonw.exe"
py = appDir & "\.venv\Scripts\python.exe"
scriptPath = """" & appDir & "\tools\run_local_server.py"""

If fso.FileExists(pyw) Then
    shell.Run """" & pyw & """ " & scriptPath, 0, False
ElseIf fso.FileExists(py) Then
    shell.Run """" & py & """ " & scriptPath, 0, False
Else
    shell.Run "pythonw " & scriptPath, 0, False
End If
