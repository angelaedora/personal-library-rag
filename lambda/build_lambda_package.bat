@echo off
REM Build Lambda deployment packages for indexer (Windows)

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set BUILD_DIR=%SCRIPT_DIR%build
set LAYER_DIR=%BUILD_DIR%\layer
set ZIP_DIR=%BUILD_DIR%\zips

echo 🔨 Building Lambda deployment packages...

REM Create directories
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
mkdir "%LAYER_DIR%\python\lib\python3.11\site-packages"
mkdir "%ZIP_DIR%"

REM Build Lambda Layer (dependencies)
echo 📦 Building Lambda layer with dependencies...
pip install -r "%SCRIPT_DIR%requirements.txt" ^
  -t "%LAYER_DIR%\python\lib\python3.11\site-packages\" ^
  --only-binary=:all: ^
  --implementation cp ^
  --python-version 311 ^
  --platform win_amd64

REM Clean up unnecessary files
echo 🧹 Cleaning up layer...
pushd "%LAYER_DIR%\python\lib\python3.11\site-packages"
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
for /d /r . %%d in (*.dist-info) do @if exist "%%d" rmdir /s /q "%%d"
popd

echo ✅ Layer built

REM Create layer zip
cd /d "%LAYER_DIR%"
powershell -Command "Compress-Archive -Path '.' -DestinationPath '%ZIP_DIR%\lambda_layer.zip' -Force"
echo 📦 Layer zip created: lambda_layer.zip

REM Build Lambda function code
echo 📝 Building Lambda function code...
set FUNC_BUILD_DIR=%BUILD_DIR%\function
mkdir "%FUNC_BUILD_DIR%"

REM Copy handler and modules
copy "%SCRIPT_DIR%indexer_handler.py" "%FUNC_BUILD_DIR%\lambda_function.py"
xcopy "%SCRIPT_DIR%indexer_modules" "%FUNC_BUILD_DIR%\indexer_modules\" /e /i

REM Create zip for function code
cd /d "%FUNC_BUILD_DIR%"
powershell -Command "Compress-Archive -Path '.' -DestinationPath '%ZIP_DIR%\indexer_lambda.zip' -Force"
echo 📦 Function zip created: indexer_lambda.zip

echo.
echo ✅ Build complete!
echo.
echo Deployment packages created:
echo   📦 %ZIP_DIR%\lambda_layer.zip
echo   📦 %ZIP_DIR%\indexer_lambda.zip
echo.
echo Next steps:
echo   1. Copy zips to Terraform directory
echo   2. Update Terraform with paths
echo   3. Run: terraform apply
echo.

REM Copy to infra directory if it exists
if exist "%SCRIPT_DIR%..\infra" (
  echo 📋 Copying to infra directory...
  copy "%ZIP_DIR%\lambda_layer.zip" "%SCRIPT_DIR%..\infra\lambda_layer.zip"
  copy "%ZIP_DIR%\indexer_lambda.zip" "%SCRIPT_DIR%..\infra\indexer_lambda.zip"
  echo ✅ Files copied to infra/
)

endlocal
