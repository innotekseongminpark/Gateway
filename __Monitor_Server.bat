call ..\____WPy64-3890\scripts\env_for_icons.bat
start uvicorn ./ieee_2030_5/__Monitor_Server:app --reload
timeout 2
start http://127.0.0.1:8000
pause