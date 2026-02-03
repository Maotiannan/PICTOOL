#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIF转换器模块
基于原始pic2gif项目重构，支持多图片转GIF动画
"""

import os
import sys
import time
import threading
import queue
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, ImageDraw
from typing import List, Optional, Callable, Dict, Any

from utils import (
    get_image_files, is_image_file, format_file_size,
    create_output_folder, safe_filename, handle_exception
)

class SimpleGifEncoder:
    """简化的GIF编码器，基于原始项目的编码逻辑"""

    def __init__(self):
        self.width = 0
        self.height = 0
        self.delay = 500
        self.repeat = 0
        self.quality = 20
        self.frames = []
        self.global_palette = None

    def setSize(self, width: int, height: int):
        """设置GIF尺寸"""
        self.width = width
        self.height = height

    def setDelay(self, delay: int):
        """设置帧延迟（毫秒）"""
        self.delay = delay

    def setRepeat(self, repeat: int):
        """设置循环次数（0为无限循环）"""
        self.repeat = repeat

    def setQuality(self, quality: int):
        """设置图片质量"""
        self.quality = quality

    def addFrame(self, image: Image.Image):
        """添加一帧"""
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)

        if image.mode != 'P':
            image = image.convert('P', palette=Image.Palette.ADAPTIVE, colors=256)

        self.frames.append(image)

    def encode(self) -> bytes:
        """编码GIF数据"""
        if not self.frames:
            raise ValueError("没有帧数据")

        # 使用内存流代替临时文件
        import io
        with io.BytesIO() as output:
            self.frames[0].save(
                output,
                format='GIF',
                save_all=True,
                append_images=self.frames[1:],
                duration=self.delay,
                loop=self.repeat if self.repeat != 0 else 0,
                optimize=True,
                quality=self.quality
            )
            return output.getvalue()

class GifConverter:
    """GIF转换器主类"""

    def __init__(self, parent_frame: ttk.Frame, config_manager,
                 message_queue: queue.Queue, status_callback: Callable):
        self.parent_frame = parent_frame
        self.config_manager = config_manager
        self.message_queue = message_queue
        self.status_callback = status_callback

        self.logger = logging.getLogger("GifConverter")

        # 状态变量
        self.image_files = []
        self.current_folder = tk.StringVar()
        self.selected_images = tk.StringVar()
        self.is_processing = False
        self.stop_requested = False

        # GIF参数变量
        self.delay_var = tk.IntVar(value=500)
        self.repeat_var = tk.IntVar(value=0)
        self.quality_var = tk.IntVar(value=20)
        
        # 验证回调
        def validate_inputs(*args):
            try:
                # 延迟不能过小
                if self.delay_var.get() < 10: self.delay_var.set(10)
                # 质量限制
                if self.quality_var.get() < 1: self.quality_var.set(1)
                if self.quality_var.get() > 100: self.quality_var.set(100)
            except:
                pass
        
        self.delay_var.trace_add('write', validate_inputs)
        self.quality_var.trace_add('write', validate_inputs)
        self.width_var = tk.IntVar(value=400)
        self.height_var = tk.IntVar(value=400)
        self.keep_ratio_var = tk.BooleanVar(value=True)

        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        """设置用户界面"""
        # 主容器
        main_container = ttk.Frame(self.parent_frame)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)

        # 左侧：文件选择和预览
        left_frame = ttk.Frame(main_container)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))

        self.create_file_selection_panel(left_frame)
        self.create_preview_panel(left_frame)

        # 右侧：参数设置
        right_frame = ttk.Frame(main_container, width=300)
        right_frame.pack(side='right', fill='y')
        right_frame.pack_propagate(False)

        self.create_settings_panel(right_frame)
        self.create_control_panel(right_frame)

    def create_file_selection_panel(self, parent):
        """创建文件选择面板"""
        # 文件夹选择
        folder_frame = ttk.LabelFrame(parent, text="选择图片文件夹", padding=10)
        folder_frame.pack(fill='x', pady=(0, 10))

        folder_select_frame = ttk.Frame(folder_frame)
        folder_select_frame.pack(fill='x')

        self.folder_entry = ttk.Entry(folder_select_frame, textvariable=self.current_folder)
        self.folder_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))

        browse_btn = ttk.Button(folder_select_frame, text="浏览", command=self.select_folder)
        browse_btn.pack(side='right')

        # 文件信息
        info_frame = ttk.Frame(folder_frame)
        info_frame.pack(fill='x', pady=(10, 0))

        self.file_count_label = ttk.Label(info_frame, text="找到 0 个图片文件")
        self.file_count_label.pack(side='left')

    def create_preview_panel(self, parent):
        """创建预览面板"""
        preview_frame = ttk.LabelFrame(parent, text="图片预览", padding=10)
        preview_frame.pack(fill='both', expand=True)

        # 创建带滚动条的画布
        canvas_frame = ttk.Frame(preview_frame)
        canvas_frame.pack(fill='both', expand=True)

        # 滚动条
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient='vertical')
        v_scrollbar.pack(side='right', fill='y')

        h_scrollbar = ttk.Scrollbar(canvas_frame, orient='horizontal')
        h_scrollbar.pack(side='bottom', fill='x')

        # 画布
        self.preview_canvas = tk.Canvas(
            canvas_frame,
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set
        )
        self.preview_canvas.pack(side='left', fill='both', expand=True)

        v_scrollbar.config(command=self.preview_canvas.yview)
        h_scrollbar.config(command=self.preview_canvas.xview)

        # 预览内容框架
        self.preview_content = ttk.Frame(self.preview_canvas)
        self.preview_canvas_window = self.preview_canvas.create_window(
            (0, 0), window=self.preview_content, anchor='nw'
        )

        self.preview_content.bind('<Configure>', self.on_preview_configure)
        self.preview_canvas.bind('<MouseWheel>', self.on_canvas_mousewheel)

    def on_preview_configure(self, event):
        """预览内容配置变化事件"""
        # 更新滚动区域
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox('all'))

    def on_canvas_mousewheel(self, event):
        """画布鼠标滚轮事件"""
        self.preview_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def create_settings_panel(self, parent):
        """创建设置面板"""
        settings_frame = ttk.LabelFrame(parent, text="GIF设置", padding=10)
        settings_frame.pack(fill='x', pady=(0, 10))

        # 帧延迟
        ttk.Label(settings_frame, text="帧延迟 (毫秒):").grid(row=0, column=0, sticky='w', pady=5)
        delay_spinbox = ttk.Spinbox(
            settings_frame, from_=50, to=5000, textvariable=self.delay_var, width=10
        )
        delay_spinbox.grid(row=0, column=1, sticky='ew', pady=5, padx=(5, 0))

        # 循环次数
        ttk.Label(settings_frame, text="循环次数:").grid(row=1, column=0, sticky='w', pady=5)
        repeat_frame = ttk.Frame(settings_frame)
        repeat_frame.grid(row=1, column=1, sticky='ew', pady=5, padx=(5, 0))

        repeat_spinbox = ttk.Spinbox(
            repeat_frame, from_=0, to=100, textvariable=self.repeat_var, width=8
        )
        repeat_spinbox.pack(side='left')

        ttk.Label(repeat_frame, text="(0=无限)").pack(side='left', padx=(5, 0))

        # 质量
        ttk.Label(settings_frame, text="图片质量:").grid(row=2, column=0, sticky='w', pady=5)
        quality_scale = ttk.Scale(
            settings_frame, from_=1, to=100, variable=self.quality_var, orient='horizontal'
        )
        quality_scale.grid(row=2, column=1, sticky='ew', pady=5, padx=(5, 0))

        self.quality_label = ttk.Label(settings_frame, text="20")
        self.quality_label.grid(row=3, column=1, sticky='w')

        quality_scale.config(command=lambda v: self.quality_label.config(text=f"{int(float(v))}"))

        # 尺寸设置
        size_frame = ttk.LabelFrame(settings_frame, text="输出尺寸", padding=5)
        size_frame.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(10, 0))

        # 宽度
        ttk.Label(size_frame, text="宽度:").grid(row=0, column=0, sticky='w', pady=2)
        width_spinbox = ttk.Spinbox(
            size_frame, from_=100, to=2000, textvariable=self.width_var, width=10
        )
        width_spinbox.grid(row=0, column=1, sticky='ew', pady=2)

        # 高度
        ttk.Label(size_frame, text="高度:").grid(row=1, column=0, sticky='w', pady=2)
        height_spinbox = ttk.Spinbox(
            size_frame, from_=100, to=2000, textvariable=self.height_var, width=10
        )
        height_spinbox.grid(row=1, column=1, sticky='ew', pady=2)

        # 保持宽高比
        keep_ratio_check = ttk.Checkbutton(
            size_frame, text="保持宽高比", variable=self.keep_ratio_var
        )
        keep_ratio_check.grid(row=2, column=0, columnspan=2, sticky='w', pady=5)

        settings_frame.columnconfigure(1, weight=1)
        size_frame.columnconfigure(1, weight=1)

    def create_control_panel(self, parent):
        """创建控制面板"""
        control_frame = ttk.LabelFrame(parent, text="操作", padding=10)
        control_frame.pack(fill='x')

        # 预览按钮
        preview_btn = ttk.Button(control_frame, text="预览首帧", command=self.preview_first_frame)
        preview_btn.pack(fill='x', pady=(0, 5))

        # 生成按钮
        self.generate_btn = ttk.Button(
            control_frame,
            text="生成GIF",
            command=self.start_generation,
            style='Success.TButton'
        )
        self.generate_btn.pack(fill='x', pady=(0, 5))

        # 停止按钮
        self.stop_btn = ttk.Button(
            control_frame,
            text="停止生成",
            command=self.stop_generation,
            state='disabled',
            style='Danger.TButton'
        )
        self.stop_btn.pack(fill='x')

    @handle_exception
    def select_folder(self):
        """选择文件夹"""
        folder_path = filedialog.askdirectory(title="选择包含图片的文件夹")
        if folder_path:

            self.current_folder.set(folder_path)
            # 立即保存路径
            self.config_manager.set('paths.last_folder', folder_path)
            if self.config_manager.get('app.auto_save', True):
                self.config_manager.save_settings()

            self.load_images()

    @handle_exception
    def load_images(self):
        """加载图片文件"""
        folder_path = self.current_folder.get()
        if not folder_path or not os.path.isdir(folder_path):
            return

        self.image_files = get_image_files(folder_path)
        self.update_preview()
        self.update_file_info()

        if self.image_files:
            self.message_queue.put({
                'type': 'status',
                'data': f"已加载 {len(self.image_files)} 个图片文件"
            })

    def update_preview(self):
        """更新预览区域"""
        # 清空现有预览
        for widget in self.preview_content.winfo_children():
            widget.destroy()

        if not self.image_files:
            ttk.Label(self.preview_content, text="请选择包含图片的文件夹").pack()
            return

        # 显示图片缩略图
        for i, image_path in enumerate(self.image_files):
            self.create_image_thumbnail(image_path, i)

    def create_image_thumbnail(self, image_path: str, index: int):
        """创建图片缩略图"""
        frame = ttk.Frame(self.preview_content)
        frame.pack(pady=5, padx=5, anchor='w')

        try:
            # 加载并调整图片大小
            image = Image.open(image_path)
            image.thumbnail((100, 100), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)

            # 图片标签
            img_label = ttk.Label(frame, image=photo)
            img_label.image = photo  # 保持引用
            img_label.pack(side='left', padx=(0, 5))

            # 文件信息
            info_frame = ttk.Frame(frame)
            info_frame.pack(side='left', fill='x', expand=True)

            # 文件名
            filename = os.path.basename(image_path)
            if len(filename) > 30:
                filename = filename[:27] + "..."
            ttk.Label(info_frame, text=filename, font=('Arial', 9, 'bold')).pack(anchor='w')

            # 文件大小
            file_size = format_file_size(os.path.getsize(image_path))
            ttk.Label(info_frame, text=file_size, font=('Arial', 8), foreground='gray').pack(anchor='w')

            # 图片尺寸
            img_size = f"{image.width}×{image.height}"
            ttk.Label(info_frame, text=img_size, font=('Arial', 8), foreground='gray').pack(anchor='w')

        except Exception as e:
            self.logger.error(f"创建缩略图失败 {image_path}: {e}")
            ttk.Label(frame, text="加载失败", foreground='red').pack(side='left')

    def update_file_info(self):
        """更新文件信息"""
        count = len(self.image_files)
        if count > 0:
            total_size = sum(os.path.getsize(f) for f in self.image_files if os.path.exists(f))
            size_text = format_file_size(total_size)
            self.file_count_label.config(text=f"找到 {count} 个图片文件 (总大小: {size_text})")
        else:
            self.file_count_label.config(text="找到 0 个图片文件")

    @handle_exception
    def preview_first_frame(self):
        """预览第一帧（调整后的大小）"""
        if not self.image_files:
            messagebox.showwarning("警告", "请先选择图片文件夹")
            return

        try:
            # 加载第一张图片
            image_path = self.image_files[0]
            image = Image.open(image_path)

            # 调整到目标尺寸
            width = self.width_var.get()
            height = self.height_var.get()

            if self.keep_ratio_var.get():
                # 保持宽高比
                image.thumbnail((width, height), Image.Resampling.LANCZOS)
            else:
                # 强制调整尺寸
                image = image.resize((width, height), Image.Resampling.LANCZOS)

            # 显示预览窗口
            self.show_preview_window(image, os.path.basename(image_path))

        except Exception as e:
            self.logger.error(f"预览失败: {e}")
            messagebox.showerror("错误", f"预览失败: {e}")

    def show_preview_window(self, image: Image.Image, title: str):
        """显示预览窗口"""
        preview_window = tk.Toplevel(self.parent_frame)
        preview_window.title(f"预览 - {title}")
        preview_window.geometry("600x500")
        preview_window.resizable(True, True)

        # 调整图片大小以适应窗口
        max_width, max_height = 580, 480
        image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)

        # 显示图片
        label = ttk.Label(preview_window, image=photo)
        label.image = photo
        label.pack(expand=True, padx=10, pady=10)

        # 信息标签
        info_text = f"尺寸: {image.width}×{image.height}"
        ttk.Label(preview_window, text=info_text).pack(pady=(0, 10))

    @handle_exception
    def start_generation(self):
        """开始生成GIF"""
        if not self.image_files:
            messagebox.showwarning("警告", "请先选择图片文件夹")
            return

        if len(self.image_files) < 2:
            messagebox.showwarning("警告", "至少需要2张图片才能生成GIF")
            return

        # 保存当前设置
        self.save_settings()

        # 禁用控件
        self.generate_btn.config(state='disabled')
        self.stop_btn.config(state='normal')

        # 启动处理线程
        self.is_processing = True
        self.stop_requested = False

        thread = threading.Thread(target=self.generate_gif_thread, daemon=True)
        thread.start()

    def generate_gif_thread(self):
        """生成GIF的线程函数"""
        try:
            # 获取输出路径
            output_folder = create_output_folder(self.current_folder.get(), "_gif")
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_filename = f"animated_gif_{timestamp}.gif"
            output_path = os.path.join(output_folder, output_filename)

            # 获取参数
            width = self.width_var.get()
            height = self.height_var.get()
            delay = self.delay_var.get()
            repeat = self.repeat_var.get()
            quality = self.quality_var.get()
            keep_ratio = self.keep_ratio_var.get()

            self.message_queue.put({
                'type': 'status',
                'data': "开始生成GIF..."
            })

            # Check available memory
            import psutil
            mem = psutil.virtual_memory()
            if mem.available < 100 * 1024 * 1024:  # Less than 100MB
                 raise MemoryError("内存不足，无法继续处理")

            # 创建GIF编码器
            encoder = SimpleGifEncoder()
            encoder.setSize(width, height)
            encoder.setDelay(delay)
            encoder.setRepeat(repeat)
            encoder.setQuality(quality)

            # 处理每一张图片
            total_images = len(self.image_files)
            for i, image_path in enumerate(self.image_files):
                if self.stop_requested:
                    break

                # Check memory periodically
                if i % 5 == 0:
                    if psutil.virtual_memory().available < 50 * 1024 * 1024:
                        raise MemoryError("内存不足，处理被终止")

                # 更新进度
                progress = (i + 1) / total_images * 100
                self.message_queue.put({
                    'type': 'progress',
                    'data': progress
                })

                self.message_queue.put({
                    'type': 'status',
                    'data': f"处理图片 {i+1}/{total_images}: {os.path.basename(image_path)}"
                })

                # 加载图片
                try:
                    image = Image.open(image_path)

                    # 调整尺寸
                    if keep_ratio:
                        # 保持宽高比
                        image.thumbnail((width, height), Image.Resampling.LANCZOS)
                        # 创建目标尺寸的画布
                        canvas = Image.new('RGB', (width, height), (255, 255, 255))
                        # 居中放置图片
                        x = (width - image.width) // 2
                        y = (height - image.height) // 2
                        canvas.paste(image, (x, y))
                        image = canvas
                    else:
                        # 强制调整尺寸
                        image = image.resize((width, height), Image.Resampling.LANCZOS)

                    # 添加到编码器
                    encoder.addFrame(image)

                except Exception as e:
                    self.logger.error(f"处理图片失败 {image_path}: {e}")

            if self.stop_requested:
                self.message_queue.put({
                    'type': 'status',
                    'data': "生成已取消"
                })
            else:
                # 生成GIF
                gif_data = encoder.encode()

                # 保存文件
                with open(output_path, 'wb') as f:
                    f.write(gif_data)

                # 完成
                self.message_queue.put({
                    'type': 'status',
                    'data': f"GIF生成完成: {output_filename}"
                })

                self.message_queue.put({
                    'type': 'info',
                    'data': f"GIF文件已保存到:\n{output_path}"
                })

                # 询问是否打开文件夹
                self.open_output_folder(output_folder)

        except Exception as e:
            self.logger.error(f"生成GIF失败: {e}")
            self.message_queue.put({
                'type': 'error',
                'data': f"生成GIF失败: {e}"
            })

        finally:
            # 恢复控件状态
            self.is_processing = False
            self.message_queue.put({
                'type': 'enable_controls',
                'data': True
            })

    def stop_generation(self):
        """停止生成"""
        self.stop_requested = True
        self.message_queue.put({
            'type': 'status',
            'data': "正在停止生成..."
        })

    def open_output_folder(self, folder_path: str):
        """打开输出文件夹"""
        try:
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(['open', folder_path])
            else:
                import subprocess
                subprocess.Popen(['xdg-open', folder_path])
        except Exception as e:
            self.logger.error(f"打开文件夹失败: {e}")

    def enable_controls(self, enable: bool = True):
        """启用/禁用控件"""
        if enable:
            self.generate_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
        else:
            self.generate_btn.config(state='disabled')
            self.stop_btn.config(state='normal')

    def load_settings(self):
        """加载设置"""
        try:
            gif_config = self.config_manager.get_section('gif')

            self.delay_var.set(gif_config.get('delay', 500))
            self.repeat_var.set(gif_config.get('repeat', 0))
            self.quality_var.set(gif_config.get('quality', 20))
            self.width_var.set(gif_config.get('width', 400))
            self.height_var.set(gif_config.get('height', 400))
            self.keep_ratio_var.set(gif_config.get('keep_ratio', True))

            self.quality_label.config(text=str(self.quality_var.get()))

        except Exception as e:
            self.logger.error(f"加载设置失败: {e}")

    def save_settings(self):
        """保存设置"""
        try:
            gif_settings = {
                'delay': self.delay_var.get(),
                'repeat': self.repeat_var.get(),
                'quality': self.quality_var.get(),
                'width': self.width_var.get(),
                'height': self.height_var.get(),
                'keep_ratio': self.keep_ratio_var.get()
            }

            self.config_manager.update_section('gif', gif_settings)

        except Exception as e:
            self.logger.error(f"保存设置失败: {e}")