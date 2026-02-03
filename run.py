#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片处理工具套件启动脚本
简化启动流程，自动检查依赖并启动应用
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 7):
        print("错误: 需要Python 3.7或更高版本")
        print(f"当前版本: {sys.version}")
        return False
    return True

def install_dependencies():
    """安装依赖包"""
    print("正在安装依赖包...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("依赖包安装完成!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"依赖包安装失败: {e}")
        print("请手动运行: pip install -r requirements.txt")
        return False

def check_dependencies():
    """检查依赖包"""
    required_packages = {
        'PIL': 'Pillow',
        'img2pdf': 'img2pdf',
        'psutil': 'psutil'
    }

    missing_packages = []
    for module_name, package_name in required_packages.items():
        try:
            __import__(module_name)
        except ImportError:
            missing_packages.append(package_name)

    if missing_packages:
        print(f"缺少依赖包: {', '.join(missing_packages)}")

        # 询问是否自动安装
        try:
            response = input("是否自动安装依赖包? (y/n): ").strip().lower()
            if response in ['y', 'yes', '是']:
                return install_dependencies()
            else:
                print("请手动安装依赖包后重试")
                return False
        except KeyboardInterrupt:
            print("\n操作取消")
            return False

    return True

def create_directories():
    """创建必要的目录"""
    directories = ['logs', 'assets']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)

def setup_logging():
    """设置日志"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "startup.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def main():
    """主函数"""
    print("图片处理工具套件 v2.0")
    print("=" * 40)

    # 检查Python版本
    if not check_python_version():
        input("按回车键退出...")
        return

    # 设置日志
    setup_logging()
    logger = logging.getLogger("Startup")

    # 创建目录
    create_directories()

    # 检查依赖
    if not check_dependencies():
        input("按回车键退出...")
        return

    # 启动应用
    try:
        logger.info("启动图片处理工具套件")
        print("正在启动应用...")

        # 导入并启动主应用
        from pic_tool_suite import main as app_main
        app_main()

    except ImportError as e:
        logger.error(f"导入模块失败: {e}")
        print(f"错误: 无法导入应用模块 - {e}")
        print("请检查文件是否完整")
        input("按回车键退出...")
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        print(f"错误: 应用启动失败 - {e}")
        input("按回车键退出...")

if __name__ == "__main__":
    main()