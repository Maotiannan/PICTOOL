#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
静默启动脚本 - 隐藏控制台窗口启动图片处理工具套件
自动保存运行日志，用于问题排查
"""

import os
import sys
import logging
import subprocess
import datetime
from pathlib import Path

def setup_logging():
    """设置日志系统"""
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 创建带有时间戳的日志文件
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"application_{timestamp}.log"

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # 仍然输出到控制台（虽然会被隐藏）
        ]
    )

    logger = logging.getLogger("SilentLauncher")
    logger.info(f"图片处理工具套件静默启动 - 日志文件: {log_file}")

    return logger, log_file

def check_dependencies():
    """检查并安装依赖"""
    logger = logging.getLogger("SilentLauncher")

    try:
        import PIL
        logger.info(f"PIL库可用: {PIL.__version__}")
    except ImportError:
        logger.error("PIL库不可用，尝试安装...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"],
                         check=True, capture_output=True, text=True)
            logger.info("PIL库安装成功")
        except subprocess.CalledProcessError as e:
            logger.error(f"PIL库安装失败: {e}")
            return False

    try:
        import img2pdf
        logger.info("img2pdf库可用")
    except ImportError:
        logger.warning("img2pdf库不可用，PDF功能将受限")

    return True

def main():
    """主函数"""
    try:
        # 设置日志
        logger, log_file = setup_logging()

        # 记录启动信息
        logger.info("=" * 50)
        logger.info("图片处理工具套件 v2.0 - 静默启动")
        logger.info(f"Python版本: {sys.version}")
        logger.info(f"工作目录: {os.getcwd()}")
        logger.info("=" * 50)

        # 检查依赖
        if not check_dependencies():
            logger.error("依赖检查失败，无法启动应用")
            return False

        # 启动主应用
        logger.info("正在启动主应用程序...")

        try:
            # 导入并启动主应用
            from pic_tool_suite import PicToolSuite

            # 创建应用实例
            app = PicToolSuite()
            logger.info("应用实例创建成功")

            # 运行应用
            app.run()

        except ImportError as e:
            logger.error(f"导入主应用失败: {e}")
            logger.error("请确保所有文件都在正确的位置")
            return False
        except Exception as e:
            logger.error(f"应用运行出错: {e}")
            logger.error("详细错误信息已记录在日志文件中")
            return False

    except Exception as e:
        # 如果连日志系统都无法设置，就输出到文件
        try:
            error_log = Path("logs") / f"startup_error_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            error_log.parent.mkdir(exist_ok=True)
            with open(error_log, 'w', encoding='utf-8') as f:
                f.write(f"启动失败: {e}\n")
                f.write(f"时间: {datetime.datetime.now()}\n")
                f.write(f"Python版本: {sys.version}\n")
                f.write(f"工作目录: {os.getcwd()}\n")
        except:
            pass
        return False

    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            # 如果启动失败，可以选择显示错误对话框
            try:
                import tkinter as tk
                from tkinter import messagebox

                root = tk.Tk()
                root.withdraw()  # 隐藏主窗口
                messagebox.showerror(
                    "启动失败",
                    "图片处理工具套件启动失败。\n"
                    "请查看logs目录下的日志文件获取详细信息。\n"
                    "或尝试手动运行 run.py 进行故障排查。"
                )
                root.destroy()
            except:
                pass
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # 最后的错误处理
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("严重错误", f"发生严重错误: {e}")
            root.destroy()
        except:
            pass