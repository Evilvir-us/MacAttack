pyinstaller.exe --onefile --add-data="include\;include" --icon=icon.ico MacAttack.pyw
copy dist\MacAttack.exe .\
pause