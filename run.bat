@echo off
echo ==========================================================
echo Starting Model-Reproducibility Registry Web Application...
echo ==========================================================
echo Opening http://localhost:8000 in your browser...
start http://localhost:8000
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000
pause
