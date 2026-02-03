#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片处理工具套件 - 统一GUI界面
整合了图片转GIF、图片转PDF、批量水印三个核心功能
"""

import os
import sys
import json
import logging
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

# 导入配置管理
try:
    from config import ConfigManager
    from utils import setup_logging, get_resource_path
    from modules.gif_converter import GifConverter
    from modules.pdf_converter import PdfConverter
    from modules.watermark_tool import WatermarkTool
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有必要的文件都在正确的位置")
    sys.exit(1)

class PicToolSuite:
    """图片处理工具套件主应用"""

    def __init__(self):
        self.root = tk.Tk()
        self.setup_variables()
        self.setup_window()
        self.setup_logging()
        self.setup_ui()
        self.load_settings()

    def setup_window(self):
        """设置主窗口"""
        self.root.title("图片处理工具套件 v2.0")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)

        # 设置图标
        try:
            icon_path = get_resource_path("assets/icon.png")
            if os.path.exists(icon_path):
                self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
        except:
            pass

        # 设置样式
        self.setup_styles()

    def setup_styles(self):
        """设置UI样式"""
        style = ttk.Style()

        # 配置主题
        current_theme = self.config_manager.get('app.theme', 'clam')
        try:
            style.theme_use(current_theme)
        except tk.TclError:
            style.theme_use('clam')

        # 自定义样式
        style.configure('Title.TLabel', font=('Microsoft YaHei', 12, 'bold'))
        style.configure('Heading.TLabel', font=('Microsoft YaHei', 10, 'bold'))
        style.configure('Info.TLabel', font=('Microsoft YaHei', 9))

        style.configure('Primary.TButton', font=('Microsoft YaHei', 9))
        style.configure('Success.TButton', font=('Microsoft YaHei', 9), background='#4CAF50')
        style.configure('Warning.TButton', font=('Microsoft YaHei', 9), background='#FF9800')
        style.configure('Danger.TButton', font=('Microsoft YaHei', 9), background='#F44336')

    def setup_logging(self):
        """设置日志系统"""
        self.logger = setup_logging("PicToolSuite")
        self.logger.info("图片处理工具套件启动")

    def setup_variables(self):
        """设置变量"""
        # 配置管理器
        self.config_manager = ConfigManager()

        # 当前选中的工具
        self.current_tool = tk.StringVar(value="watermark")

        # 通用变量
        self.current_folder = tk.StringVar()
        self.status_text = tk.StringVar(value="就绪")
        self.progress_var = tk.DoubleVar()

        # 工具实例
        self.tools = {}

        # 消息队列（用于线程间通信）
        self.message_queue = queue.Queue()

    def setup_ui(self):
        """设置用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # 创建顶部工具栏
        self.create_toolbar(main_frame)

        # 创建主要内容区域
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill='both', expand=True, pady=(10, 0))

        # 创建左侧工具选择面板
        self.create_tool_selector(content_frame)

        # 创建右侧工作区域
        self.create_workspace(content_frame)

        # 创建底部状态栏
        self.create_statusbar(main_frame)

        # 初始化工具
        self.initialize_tools()

    def create_toolbar(self, parent):
        """创建工具栏"""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', pady=(0, 10))

        # 左侧：应用标题
        title_label = ttk.Label(toolbar, text="图片处理工具套件", style='Title.TLabel')
        title_label.pack(side='left')

        # 右侧：通用按钮


        help_btn = ttk.Button(toolbar, text="帮助", command=self.show_help)
        help_btn.pack(side='right', padx=(5, 0))

        about_btn = ttk.Button(toolbar, text="关于", command=self.show_about)
        about_btn.pack(side='right', padx=(5, 0))

    def create_tool_selector(self, parent):
        """创建工具选择面板"""
        selector_frame = ttk.LabelFrame(parent, text="工具选择", padding=10)
        selector_frame.pack(side='left', fill='y', padx=(0, 10))

        # 工具选项
        tools = [
            ("watermark", "批量水印", "为图片批量添加水印"),
            ("gif", "GIF制作", "将多张图片制作成GIF动画"),
            ("pdf", "PDF转换", "将图片转换为PDF文档")
        ]

        for tool_id, tool_name, tool_desc in tools:
            frame = ttk.Frame(selector_frame)
            frame.pack(fill='x', pady=5)

            rb = ttk.Radiobutton(
                frame,
                text=tool_name,
                variable=self.current_tool,
                value=tool_id,
                command=self.on_tool_changed
            )
            rb.pack(anchor='w')

            desc_label = ttk.Label(frame, text=tool_desc, style='Info.TLabel', foreground='gray')
            desc_label.pack(anchor='w', padx=(20, 0))

    def create_workspace(self, parent):
        """创建工作区域"""
        # 创建Notebook用于不同工具的工作区
        self.workspace = ttk.Notebook(parent)
        self.workspace.pack(fill='both', expand=True)

        # 为每个工具创建一个框架
        self.tool_frames = {}

        # 水印工具框架
        self.tool_frames['watermark'] = ttk.Frame(self.workspace)
        self.workspace.add(self.tool_frames['watermark'], text="批量水印")

        # GIF工具框架
        self.tool_frames['gif'] = ttk.Frame(self.workspace)
        self.workspace.add(self.tool_frames['gif'], text="GIF制作")

        # PDF工具框架
        self.tool_frames['pdf'] = ttk.Frame(self.workspace)
        self.workspace.add(self.tool_frames['pdf'], text="PDF转换")

        # 绑定标签切换事件
        self.workspace.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def create_statusbar(self, parent):
        """创建状态栏"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill='x', pady=(10, 0))

        # 状态文本
        status_label = ttk.Label(status_frame, textvariable=self.status_text)
        status_label.pack(side='left')

        # 进度条
        progress_bar = ttk.Progressbar(
            status_frame,
            variable=self.progress_var,
            length=200,
            mode='determinate'
        )
        progress_bar.pack(side='right', padx=(10, 0))

        # 进度百分比
        self.progress_label = ttk.Label(status_frame, text="0%")
        self.progress_label.pack(side='right', padx=(5, 0))

    def initialize_tools(self):
        """初始化工具"""
        try:
            # 初始化水印工具
            self.tools['watermark'] = WatermarkTool(
                self.tool_frames['watermark'],
                self.config_manager,
                self.message_queue,
                self.update_status
            )

            # 初始化GIF工具
            self.tools['gif'] = GifConverter(
                self.tool_frames['gif'],
                self.config_manager,
                self.message_queue,
                self.update_status
            )

            # 初始化PDF工具
            self.tools['pdf'] = PdfConverter(
                self.tool_frames['pdf'],
                self.config_manager,
                self.message_queue,
                self.update_status
            )

            self.logger.info("所有工具初始化完成")

        except Exception as e:
            self.logger.error(f"工具初始化失败: {e}")
            messagebox.showerror("错误", f"工具初始化失败: {e}")

    def on_tool_changed(self):
        """工具选择改变事件"""
        tool_id = self.current_tool.get()

        # 切换到对应的标签页
        for i, tab_id in enumerate(['watermark', 'gif', 'pdf']):
            if tab_id == tool_id:
                self.workspace.select(i)
                break

        self.logger.info(f"切换到工具: {tool_id}")
        self.update_status(f"已切换到: {self.get_tool_name(tool_id)}")

    def on_tab_changed(self, event):
        """标签页切换事件"""
        current_tab = event.widget.tab('current')['text']
        tool_mapping = {
            "批量水印": "watermark",
            "GIF制作": "gif",
            "PDF转换": "pdf"
        }

        tool_id = tool_mapping.get(current_tab, "watermark")
        self.current_tool.set(tool_id)

    def get_tool_name(self, tool_id):
        """获取工具名称"""
        names = {
            "watermark": "批量水印",
            "gif": "GIF制作",
            "pdf": "PDF转换"
        }
        return names.get(tool_id, "未知工具")

    def update_status(self, message):
        """更新状态栏"""
        self.status_text.set(message)
        self.root.update_idletasks()

    def update_progress(self, value):
        """更新进度条"""
        self.progress_var.set(value)
        self.progress_label.config(text=f"{int(value)}%")
        self.root.update_idletasks()

    def check_message_queue(self):
        """检查消息队列"""
        try:
            while True:
                message = self.message_queue.get_nowait()
                self.handle_message(message)
        except queue.Empty:
            pass
        finally:
            # 继续检查队列
            self.root.after(100, self.check_message_queue)

    def handle_message(self, message):
        """处理消息"""
        if not isinstance(message, dict):
            return

        msg_type = message.get('type')
        msg_data = message.get('data')

        if msg_type == 'status':
            self.update_status(msg_data)
        elif msg_type == 'progress':
            self.update_progress(msg_data)
        elif msg_type == 'error':
            messagebox.showerror("错误", msg_data)
        elif msg_type == 'info':
            messagebox.showinfo("信息", msg_data)
        elif msg_type == 'warning':
            messagebox.showwarning("警告", msg_data)
        elif msg_type == 'enable_controls':
            # 通知所有工具启用/禁用控件
            for tool in self.tools.values():
                if hasattr(tool, 'enable_controls'):
                    tool.enable_controls(msg_data)

    def load_settings(self):
        """加载设置"""
        try:
            self.config_manager.load_settings()
            self.logger.info("设置加载完成")
        except Exception as e:
            self.logger.error(f"加载设置失败: {e}")

    def save_settings(self):
        """保存设置"""
        try:
            self.config_manager.save_settings()
            self.logger.info("设置保存完成")
        except Exception as e:
            self.logger.error(f"保存设置失败: {e}")
            messagebox.showerror("错误", f"保存设置失败: {e}")

    def show_settings(self):
        """显示设置对话框"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("设置")
        settings_window.geometry("400x300")
        settings_window.resizable(False, False)

        # 居中显示
        settings_window.transient(self.root)
        settings_window.grab_set()

        # 主容器
        main_frame = ttk.Frame(settings_window, padding=20)
        main_frame.pack(fill='both', expand=True)

        # 主题设置
        theme_frame = ttk.LabelFrame(main_frame, text="外观", padding=10)
        theme_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(theme_frame, text="主题:").pack(side='left')
        
        current_theme = self.config_manager.get('app.theme', 'clam')
        theme_var = tk.StringVar(value=current_theme)
        
        # 获取可用主题
        available_themes = ttk.Style().theme_names()
        theme_combo = ttk.Combobox(
            theme_frame, 
            textvariable=theme_var, 
            values=sorted(list(available_themes)),
            state='readonly'
        )
        theme_combo.pack(side='left', padx=(10, 0), fill='x', expand=True)

        # 行为设置
        behavior_frame = ttk.LabelFrame(main_frame, text="行为", padding=10)
        behavior_frame.pack(fill='x', pady=(0, 10))

        auto_save_var = tk.BooleanVar(value=self.config_manager.get('app.auto_save', True))
        ttk.Checkbutton(
            behavior_frame, 
            text="退出时自动保存设置", 
            variable=auto_save_var
        ).pack(anchor='w')

        remember_path_var = tk.BooleanVar(value=self.config_manager.get('app.remember_last_folder', True))
        ttk.Checkbutton(
            behavior_frame, 
            text="记住使用的文件夹", 
            variable=remember_path_var
        ).pack(anchor='w')

        # 按钮区域
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        def save_and_close():
            # 保存设置
            self.config_manager.set('app.theme', theme_var.get())
            self.config_manager.set('app.auto_save', auto_save_var.get())
            self.config_manager.set('app.remember_last_folder', remember_path_var.get())
            self.config_manager.save_settings()
            
            # 提示重启
            if theme_var.get() != current_theme:
                messagebox.showinfo("提示", "主题更改将在下次启动时生效")
            
            settings_window.destroy()

        ttk.Button(btn_frame, text="保存", command=save_and_close).pack(side='right')
        ttk.Button(btn_frame, text="取消", command=settings_window.destroy).pack(side='right', padx=(0, 10))

    def show_help(self):
        """显示帮助对话框"""
        help_text = """
图片处理工具套件 v2.0

功能介绍：
1. 批量水印 - 为图片批量添加文字水印
2. GIF制作 - 将多张图片制作成GIF动画
3. PDF转换 - 将图片转换为PDF文档

使用方法：
1. 从左侧选择要使用的工具
2. 按照工具界面的提示进行操作
3. 点击开始处理按钮执行任务

技术支持：毛天楠
更新时间：2026/1/15
        """
        messagebox.showinfo("帮助", help_text.strip())

    def show_about(self):
        """显示关于对话框"""
        about_text = """
图片处理工具套件 v2.0

开发者：毛天楠
版本：2.0.0
更新日期：2026

这是一个集成了多种图片处理功能的
综合性工具软件，旨在为用户提供便捷
高效的图片处理体验。

主要功能：
- 批量水印添加
- GIF动画制作
- PDF文档转换

版权所有 © 毛天楠
        """
        messagebox.showinfo("关于", about_text.strip())

    def on_closing(self):
        """窗口关闭事件"""
        self.save_settings()
        self.logger.info("程序正常退出")
        self.root.destroy()

    def run(self):
        """运行应用"""
        # 启动消息队列检查
        self.root.after(100, self.check_message_queue)

        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 启动主循环
        self.root.mainloop()

def main():
    """主函数"""
    try:
        # DEBUG: 确认当前运行的代码版本
        # DEBUG: 确认当前运行的代码版本

        app = PicToolSuite()
        app.run()
    except Exception as e:
        logging.error(f"程序启动失败: {e}")
        messagebox.showerror("错误", f"程序启动失败: {e}")

if __name__ == "__main__":
    main()