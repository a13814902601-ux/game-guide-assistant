' Start the game guide overlay without a console window.
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
base = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = base
pythonw = fso.BuildPath(fso.GetParentFolderName(base), ".venv\Scripts\pythonw.exe")
script = fso.BuildPath(base, "main.py")
If Not fso.FileExists(pythonw) Then
  MsgBox "Project .venv not found. Install dependencies first.", 16, "Game Guide Overlay"
  WScript.Quit 1
End If
q = Chr(34)
sh.Run q & pythonw & q & " " & q & script & q, 0, False
