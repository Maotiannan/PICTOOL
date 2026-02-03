#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用测试脚本
用于测试图片处理工具套件的基本功能
"""

import sys
import os
import traceback
from pathlib import Path

def test_imports():
    """测试模块导入"""
    print("测试模块导入...")
    try:
        # 测试基础模块
        import config
        import utils
        print("[OK] 基础模块导入成功")

        # 测试工具模块
        from modules.gif_converter import GifConverter
        from modules.pdf_converter import PdfConverter
        from modules.watermark_tool import WatermarkTool
        print("[OK] 工具模块导入成功")

        # 测试主应用
        import pic_tool_suite
        print("[OK] 主应用模块导入成功")

        return True
    except ImportError as e:
        print(f"[ERROR] 模块导入失败: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"[ERROR] 导入测试失败: {e}")
        traceback.print_exc()
        return False

def test_dependencies():
    """测试依赖库"""
    print("\n测试依赖库...")
    try:
        import PIL
        print(f"[OK] PIL版本: {PIL.__version__}")

        try:
            import img2pdf
            print("[OK] img2pdf可用")
        except ImportError:
            print("[WARNING] img2pdf不可用 (PDF功能将受限)")

        try:
            import psutil
            print(f"[OK] psutil版本: {psutil.__version__}")
        except ImportError:
            print("[INFO] psutil不可用 (非必需)")

        return True
    except ImportError as e:
        print(f"[ERROR] 依赖库测试失败: {e}")
        return False

def test_gui():
    """测试GUI组件"""
    print("\n测试GUI组件...")
    try:
        import tkinter as tk
        print("[OK] tkinter可用")

        # 测试是否能创建根窗口
        root = tk.Tk()
        root.withdraw()  # 隐藏窗口
        root.destroy()
        print("[OK] GUI组件测试成功")

        return True
    except Exception as e:
        print(f"[ERROR] GUI测试失败: {e}")
        return False

def test_file_structure():
    """测试文件结构"""
    print("\n测试文件结构...")
    required_files = [
        'pic_tool_suite.py',
        'config.py',
        'utils.py',
        'run.py',
        'requirements.txt',
        'README.md'
    ]

    required_dirs = [
        'modules',
        'logs'
    ]

    missing_files = []
    missing_dirs = []

    for file in required_files:
        if os.path.isfile(file):
            print(f"[OK] {file}")
        else:
            missing_files.append(file)
            print(f"[ERROR] {file} 缺失")

    for dir in required_dirs:
        if os.path.isdir(dir):
            print(f"[OK] {dir}/")
        else:
            missing_dirs.append(dir)
            print(f"[ERROR] {dir}/ 缺失")

    return len(missing_files) == 0 and len(missing_dirs) == 0

def main():
    """主测试函数"""
    print("图片处理工具套件 - 系统测试")
    print("=" * 50)

    tests = [
        ("文件结构", test_file_structure),
        ("模块导入", test_imports),
        ("依赖库", test_dependencies),
        ("GUI组件", test_gui)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        if test_func():
            passed += 1
            print(f"[OK] {test_name} 测试通过")
        else:
            print(f"[ERROR] {test_name} 测试失败")

    print("\n" + "=" * 50)
    print(f"测试结果: {passed}/{total} 通过")

    if passed == total:
        print("[SUCCESS] 所有测试通过！应用可以正常运行。")
        print("\n启动方法:")
        print("1. 双击运行 run.py")
        print("2. 或在命令行运行: python pic_tool_suite.py")
        return True
    else:
        print("[FAILED] 部分测试失败，请检查上述错误信息。")
        return False

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            input("\n按回车键退出...")
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中发生未预期的错误: {e}")
        traceback.print_exc()
        input("按回车键退出...")