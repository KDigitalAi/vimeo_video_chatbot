@echo off
echo Testing VS Code Live Server Configuration...
echo.

echo 1. Make sure VS Code Live Server extension is installed
echo 2. Right-click on index.html in the project root
echo 3. Select "Open with Live Server"
echo 4. The chatbot should open directly at http://127.0.0.1:5500
echo.

echo Alternative: Right-click on frontend/index.html and select "Open with Live Server"
echo This will serve directly from the frontend folder.
echo.

echo Press any key to open the project in VS Code...
pause > nul

code .
