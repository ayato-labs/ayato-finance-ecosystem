@echo off
echo Running daily differential update...
.venv\Scripts\python main.py sync --symbols DFF UNRATE
pause
