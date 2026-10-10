@echo off
setlocal
echo ============================================================
echo Provisioning Intel 1st-Party OpenVINO NPU Environment (.venv-npu)
echo ============================================================

set VENV_DIR=%~dp0.venv-npu

if not exist "%VENV_DIR%" (
    echo Creating virtualenv with Python 3.12...
    py -3.12 -m venv "%VENV_DIR%"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment with py -3.12.
        exit /b %ERRORLEVEL%
    )
)

echo Activating .venv-npu...
call "%VENV_DIR%\Scripts\activate.bat"

echo Upgrading pip and wheel...
python -m pip install --upgrade pip wheel setuptools --quiet

echo Installing Intel 1st-party OpenVINO and OpenVINO GenAI...
pip install openvino openvino-genai --quiet

echo Verifying OpenVINO installation and available devices...
python -c "import openvino as ov; core = ov.Core(); print('[SUCCESS] OpenVINO installed successfully! Available devices:', core.available_devices)"

echo ============================================================
echo Setup complete. .venv-npu is ready for Intel AI Boost NPU execution.
echo ============================================================
endlocal
