#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桌面快捷方式创建器
自动在桌面创建图片处理工具套件的快捷方式
"""

import os
import sys
import shutil
from pathlib import Path
import platform

def get_desktop_path():
    """获取桌面路径"""
    system = platform.system().lower()

    if system == "windows":
        import winreg
        try:
            # 从注册表获取桌面路径
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                              r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
            desktop_path = winreg.QueryValueEx(key, "Desktop")[0]
            winreg.CloseKey(key)
            return desktop_path
        except:
            # 备用方案
            return os.path.join(os.path.expanduser("~"), "Desktop")
    elif system == "darwin":  # macOS
        return os.path.join(os.path.expanduser("~"), "Desktop")
    else:  # Linux
        return os.path.join(os.path.expanduser("~"), "Desktop")

def create_windows_shortcut(target_path, shortcut_path, working_dir=None, icon_path=None):
    """创建Windows快捷方式"""
    try:
        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = target_path
        if working_dir:
            shortcut.WorkingDirectory = working_dir
        if icon_path and os.path.exists(icon_path):
            shortcut.IconLocation = icon_path
        shortcut.Description = "图片处理工具套件 v2.0 - 批量水印、GIF制作、PDF转换"
        shortcut.Save()
        return True
    except ImportError:
        # 如果没有win32com，使用简单的方法
        try:
            import os
            import subprocess

            # 创建批处理文件作为快捷方式
            bat_content = f'''@echo off
cd /d "{working_dir or os.path.dirname(target_path)}"
"{target_path}"
'''
            with open(shortcut_path, 'w', encoding='utf-8') as f:
                f.write(bat_content)
            return True
        except:
            return False

def create_linux_launcher(target_path, launcher_path, working_dir=None):
    """创建Linux桌面启动器"""
    desktop_content = f'''[Desktop Entry]
Version=1.0
Type=Application
Name=图片处理工具套件
Comment=批量水印、GIF制作、PDF转换
Exec=python "{target_path}"
Path={working_dir or os.path.dirname(target_path)}
Terminal=false
Categories=Graphics;Photography;
'''

    try:
        with open(launcher_path, 'w', encoding='utf-8') as f:
            f.write(desktop_content)
        os.chmod(launcher_path, 0o755)  # 设置可执行权限
        return True
    except:
        return False

def create_macos_launcher(target_path, launcher_path, working_dir=None):
    """创建macOS应用包"""
    app_name = "图片处理工具套件.app"
    app_path = os.path.join(os.path.dirname(launcher_path), app_name)

    try:
        # 创建应用包结构
        contents_dir = os.path.join(app_path, "Contents")
        macos_dir = os.path.join(contents_dir, "MacOS")
        resources_dir = os.path.join(contents_dir, "Resources")

        os.makedirs(macos_dir, exist_ok=True)
        os.makedirs(resources_dir, exist_ok=True)

        # 创建Info.plist
        info_plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>图片处理工具套件</string>
    <key>CFBundleExecutable</key>
    <string>launcher.sh</string>
    <key>CFBundleIconFile</key>
    <string>app.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.pictool.suite</string>
    <key>CFBundleName</key>
    <string>图片处理工具套件</string>
    <key>CFBundleVersion</key>
    <string>2.0.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
'''

        with open(os.path.join(contents_dir, "Info.plist"), 'w', encoding='utf-8') as f:
            f.write(info_plist)

        # 创建启动脚本
        launcher_script = f'''#!/bin/bash
cd "{working_dir or os.path.dirname(target_path)}"
"{sys.executable}" "{target_path}"
'''

        with open(os.path.join(macos_dir, "launcher.sh"), 'w', encoding='utf-8') as f:
            f.write(launcher_script)
        os.chmod(os.path.join(macos_dir, "launcher.sh"), 0o755)

        return True
    except:
        return False

def main():
    """主函数"""
    print("创建桌面快捷方式...")

    # 获取当前脚本所在目录
    current_dir = os.path.abspath(os.path.dirname(__file__))

    # 目标文件路径
    target_file = os.path.join(current_dir, "start_silent.pyw")

    # 如果静默启动文件不存在，使用run.py
    if not os.path.exists(target_file):
        target_file = os.path.join(current_dir, "run.py")

    if not os.path.exists(target_file):
        print("错误: 找不到启动文件")
        return False

    # 获取桌面路径
    desktop_path = get_desktop_path()

    system = platform.system().lower()
    success = False

    if system == "windows":
        # Windows快捷方式
        shortcut_name = "图片处理工具套件.lnk"
        shortcut_path = os.path.join(desktop_path, shortcut_name)

        # 尝试创建.lnk快捷方式
        success = create_windows_shortcut(
            target_file,
            shortcut_path,
            current_dir
        )

        if success:
            print(f"[OK] Windows快捷方式已创建: {shortcut_path}")
        else:
            # 创建批处理快捷方式
            bat_name = "图片处理工具套件.bat"
            bat_path = os.path.join(desktop_path, bat_name)

            bat_content = f'''@echo off
title 图片处理工具套件
cd /d "{current_dir}"
echo 正在启动图片处理工具套件...
"{sys.executable}" "{target_file}"
if errorlevel 1 (
    echo.
    echo 程序启动失败，请检查错误信息
    pause
)
'''

            with open(bat_path, 'w', encoding='utf-8') as f:
                f.write(bat_content)

            print(f"[OK] Windows批处理快捷方式已创建: {bat_path}")
            success = True

    elif system == "darwin":  # macOS
        launcher_name = "图片处理工具套件.desktop"
        launcher_path = os.path.join(desktop_path, launcher_name)

        success = create_linux_launcher(target_file, launcher_path, current_dir)

        if success:
            print(f"[OK] macOS桌面启动器已创建: {launcher_path}")

    else:  # Linux
        launcher_name = "图片处理工具套件.desktop"
        launcher_path = os.path.join(desktop_path, launcher_name)

        success = create_linux_launcher(target_file, launcher_path, current_dir)

        if success:
            print(f"[OK] Linux桌面启动器已创建: {launcher_path}")

    if success:
        print("\n[SUCCESS] 快捷方式创建成功！")
        print("您现在可以直接从桌面启动图片处理工具套件。")
        print(f"快捷方式位置: {desktop_path}")

        # 显示使用说明
        print("\n使用说明:")
        print("1. 双击桌面快捷方式启动应用")
        print("2. 应用运行时日志会保存在 logs/ 目录")
        print("3. 如遇问题，请查看最新的日志文件")

    else:
        print("[FAILED] 快捷方式创建失败")
        print("请手动创建快捷方式指向:")
        print(f"   {target_file}")

    return success

if __name__ == "__main__":
    try:
        main()
        input("\n按回车键退出...")
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"创建快捷方式时出错: {e}")
        input("按回车键退出...")