@echo off
chcp 65001 >nul
title 创建桌面快捷方式

echo.
echo =================================================
echo     图片处理工具套件 - 桌面快捷方式创建器
echo =================================================
echo.

:: 检查Python是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python
    echo.
    pause
    exit /b 1
)

echo [信息] Python环境检查通过
echo.

:: 切换到脚本所在目录
cd /d "%~dp0"
echo [信息] 工作目录: %CD%
echo.

:: 运行快捷方式创建脚本
echo [信息] 正在创建桌面快捷方式...
echo.

python create_shortcut.py

echo.
echo =================================================
echo 操作完成！按任意键退出...
pause >nul