Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Starting Model-Reproducibility Registry Web Application..." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Start-Process "http://localhost:8000"
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000
