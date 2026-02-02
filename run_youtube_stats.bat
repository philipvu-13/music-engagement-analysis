@echo off
echo Starting YouTube stats job...

cd C:\Users\phili\Desktop\dont-be-dumb-analysis
echo Current directory:
cd

python scripts\03_pull_youtube_stats.py

echo.
echo Script finished. Press any key to close.
pause

