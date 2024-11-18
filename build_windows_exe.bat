pyinstaller.exe --onefile --add-data="include\;include" --icon=icon.ico --hidden-import=pygame MacAttack.pyw
copy dist\MacAttack.exe .\
pause