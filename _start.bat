@echo off
start "Addin server" cmd /k "cd /d D:\inktolatex\addin && python serve.py"
start "Backend server" cmd /k "cd /d D:\inktolatex\backend && python main.py"
