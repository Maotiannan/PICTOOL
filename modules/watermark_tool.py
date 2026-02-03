#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
水印工具模块
基于原始picaddmark项目重构，支持批量图片水印添加
"""

import os
import sys
import time
import threading
import queue
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageOps, ExifTags, ImageStat
from typing import List, Optional, Callable, Dict, Any, Tuple

from utils import (
    get_image_files, is_image_file, format_file_size,
    create_output_folder, safe_filename, handle_exception,
    get_exif_datetime, is_chinese_char, contains_chinese
)

class WatermarkTool:
    """水印工具主类"""

    def __init__(self, parent_frame: ttk.Frame, config_manager,
                 message_queue: queue.Queue, status_callback: Callable):
        self.parent_frame = parent_frame
        self.config_manager = config_manager
        self.message_queue = message_queue
        self.status_callback = status_callback

        self.logger = logging.getLogger("WatermarkTool")

        # 字体
        self.font_chinese = None
        self.font_english = None
        self.init_fonts()

        # 状态变量
        self.image_files = []
        self.current_folder = tk.StringVar()
        self.is_processing = False
        self.stop_requested = False

        # 水印参数变量
        self.watermark_text = tk.StringVar(value="MU Group Leo: +86 13819858718")
        self.font_size = tk.IntVar(value=40)
        self.opacity = tk.IntVar(value=80)
        self.watermark_color = [255, 255, 0]  # 黄色
        self.position_var = tk.StringVar(value="中心")
        self.multi_size_var = tk.BooleanVar(value=True)
        self.multi_size_var = tk.BooleanVar(value=True)
        self.high_contrast_var = tk.BooleanVar(value=True)

        # 选中项
        self.selected_index = -1

        self.setup_ui()
        self.load_settings()

    def init_fonts(self):
        """初始化字体"""
        try:
            # 英文字体
            english_fonts = ["arial.ttf", "Arial", "LiberationSans-Regular.ttf", "DejaVuSans.ttf"]
            for font_name in english_fonts:
                try:
                    ImageFont.truetype(font_name, 12)
                    self.font_english = font_name
                    break
                except (IOError, OSError):
                    continue

            if not self.font_english:
                self.font_english = ImageFont.load_default()

            # 中文字体
            chinese_fonts = ["simhei.ttf", "SimHei", "msyh.ttc", "Microsoft YaHei", "simsun.ttc", "SimSun"]
            for font_name in chinese_fonts:
                try:
                    ImageFont.truetype(font_name, 12)
                    self.font_chinese = font_name
                    break
                except (IOError, OSError):
                    continue

            if not self.font_chinese:
                self.font_chinese = ImageFont.load_default()

            self.logger.info(f"字体初始化完成 - 英文: {self.font_english}, 中文: {self.font_chinese}")

        except Exception as e:
            self.logger.error(f"字体初始化失败: {e}")
            self.font_english = ImageFont.load_default()
            self.font_chinese = ImageFont.load_default()

    def setup_ui(self):
        """设置用户界面"""
        # 主容器
        main_container = ttk.Frame(self.parent_frame)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)

        # 左侧：水印设置
        left_frame = ttk.Frame(main_container)
        left_frame.pack(side='left', fill='y', padx=(0, 10))

        self.create_watermark_settings_panel(left_frame)

        # 右侧：文件选择和预览
        right_frame = ttk.Frame(main_container)
        right_frame.pack(side='right', fill='both', expand=True)

        self.create_file_panel(right_frame)

    def create_watermark_settings_panel(self, parent):
        """创建水印设置面板"""
        # 水印文本
        text_frame = ttk.LabelFrame(parent, text="水印文本", padding=10)
        text_frame.pack(fill='x', pady=(0, 10))

        text_entry = ttk.Entry(text_frame, textvariable=self.watermark_text, width=30)
        text_entry.pack(fill='x', pady=(0, 5))

        help_label = ttk.Label(text_frame, text="支持 {exif_date} 占位符", foreground='gray', font=('Arial', 8))
        help_label.pack(anchor='w')

        # 字体设置
        font_frame = ttk.LabelFrame(parent, text="字体设置", padding=10)
        font_frame.pack(fill='x', pady=(0, 10))

        # 字体大小 (添加验证)
        size_frame = ttk.Frame(font_frame)
        size_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(size_frame, text="字体大小:").pack(side='left')
        
        def validate_size(*args):
            try:
                val = self.font_size.get()
                if val < 1: self.font_size.set(1)
            except:
                pass
        self.font_size.trace_add('write', validate_size)
        
        ttk.Spinbox(size_frame, from_=10, to=200, textvariable=self.font_size, width=10).pack(side='right')

        # 多尺寸适配
        multi_size_check = ttk.Checkbutton(
            font_frame, text="多尺寸适配", variable=self.multi_size_var
        )
        multi_size_check.pack(anchor='w', pady=(5, 0))

        # 颜色和透明度
        style_frame = ttk.LabelFrame(parent, text="样式设置", padding=10)
        style_frame.pack(fill='x', pady=(0, 10))

        # 透明度 (添加验证)
        opacity_frame = ttk.Frame(style_frame)
        opacity_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(opacity_frame, text="透明度:").pack(side='left')
        
        # 验证函数
        def validate_opacity(*args):
             try:
                 val = self.opacity.get()
                 if val < 0: self.opacity.set(0)
                 if val > 100: self.opacity.set(100)
                 self.opacity_label.config(text=f"{int(self.opacity.get())}%")
             except:
                 pass
        
        self.opacity.trace_add('write', validate_opacity)

        opacity_scale = ttk.Scale(
            opacity_frame, from_=0, to=100, variable=self.opacity, orient='horizontal', length=150
        )
        opacity_scale.pack(side='left', padx=(5, 10))
        self.opacity_label = ttk.Label(opacity_frame, text="80%")
        self.opacity_label.pack(side='left')



        # 颜色选择
        color_frame = ttk.Frame(style_frame)
        color_frame.pack(fill='x', pady=(5, 0))
        ttk.Label(color_frame, text="水印颜色:").pack(side='left')
        self.color_button = tk.Button(
            color_frame,
            text="选择颜色",
            bg=self.rgb_to_hex(self.watermark_color),
            fg=self.get_contrast_color(self.watermark_color),
            command=self.choose_color,
            width=15
        )
        self.color_button.pack(side='left', padx=(5, 0))

        # 高对比度模式
        contrast_check = ttk.Checkbutton(
            style_frame, text="高对比度模式", variable=self.high_contrast_var
        )
        contrast_check.pack(anchor='w', pady=(10, 0))

        # 位置设置
        position_frame = ttk.LabelFrame(parent, text="位置设置", padding=10)
        position_frame.pack(fill='x', pady=(0, 10))

        position_combo = ttk.Combobox(
            position_frame,
            textvariable=self.position_var,
            values=["左上角", "右上角", "左下角", "右下角", "中心"],
            state='readonly',
            width=20
        )
        position_combo.pack(fill='x')

        # 预览和操作按钮
        action_frame = ttk.LabelFrame(parent, text="操作", padding=10)
        action_frame.pack(fill='x')

        preview_btn = ttk.Button(action_frame, text="预览水印", command=self.preview_watermark)
        preview_btn.pack(fill='x', pady=(0, 5))

        save_btn = ttk.Button(action_frame, text="保存设置", command=self.save_settings)
        save_btn.pack(fill='x')

    def create_file_panel(self, parent):
        """创建文件面板"""
        # 文件夹选择
        folder_frame = ttk.LabelFrame(parent, text="选择图片文件夹", padding=10)
        folder_frame.pack(fill='x', pady=(0, 10))

        folder_select_frame = ttk.Frame(folder_frame)
        folder_select_frame.pack(fill='x')

        self.folder_entry = ttk.Entry(folder_select_frame, textvariable=self.current_folder)
        self.folder_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))

        browse_btn = ttk.Button(folder_select_frame, text="浏览", command=self.select_folder)
        browse_btn.pack(side='right')

        # 文件列表
        list_frame = ttk.LabelFrame(parent, text="图片列表", padding=10)
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        # 创建Treeview
        columns = ('文件名', '尺寸', '大小')
        self.image_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)

        # 设置列标题
        self.image_tree.heading('文件名', text='文件名')
        self.image_tree.heading('尺寸', text='尺寸')
        self.image_tree.heading('大小', text='大小')

        # 设置列宽
        self.image_tree.column('文件名', width=150)
        self.image_tree.column('尺寸', width=80)
        self.image_tree.column('大小', width=80)

        # 滚动条
        v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.image_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient='horizontal', command=self.image_tree.xview)
        self.image_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # 布局
        self.image_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        # 绑定事件
        self.image_tree.bind('<<TreeviewSelect>>', self.on_tree_select)

        # 文件信息
        info_frame = ttk.Frame(list_frame)
        info_frame.grid(row=2, column=0, columnspan=2, sticky='w', pady=(5, 0))
        self.file_count_label = ttk.Label(info_frame, text="找到 0 个图片文件")
        self.file_count_label.pack(side='left')

        # 预览区域 (改为右下角小窗口或保持在右侧但使用选中图片)
        preview_frame = ttk.LabelFrame(parent, text="预览", padding=10)
        preview_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # 限制预览高度
        preview_frame.pack_propagate(False)
        preview_frame.configure(height=200)

        self.preview_canvas = tk.Canvas(preview_frame, bg='white')
        self.preview_canvas.pack(fill='both', expand=True)
        self.preview_info = ttk.Label(preview_frame, text="请选择图片进行预览", foreground='gray')
        self.preview_info.pack(pady=5)

        # 控制按钮
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill='x', side='bottom', pady=10)

        self.process_btn = ttk.Button(
            control_frame,
            text="开始处理",
            command=self.start_processing,
            style='Success.TButton'
        )
        self.process_btn.pack(side='left', padx=(0, 10))

        self.stop_btn = ttk.Button(
            control_frame,
            text="停止处理",
            command=self.stop_processing,
            state='disabled',
            style='Danger.TButton'
        )
        self.stop_btn.pack(side='left')

    def update_image_list(self):
        """更新图片列表"""
        # 清空现有项目
        for item in self.image_tree.get_children():
            self.image_tree.delete(item)

        # 添加图片项目
        for i, image_path in enumerate(self.image_files):
            try:
                filename = os.path.basename(image_path)
                file_size = format_file_size(os.path.getsize(image_path))
                # 简单加载尺寸，优化性能
                with Image.open(image_path) as img:
                     size_text = f"{img.width}×{img.height}"
                
                self.image_tree.insert('', 'end', iid=str(i), values=(filename, size_text, file_size))
            except Exception as e:
                self.logger.error(f"读取图片信息失败 {image_path}: {e}")

    def on_tree_select(self, event):
        """树形控件选择事件"""
        selection = self.image_tree.selection()
        if selection:
            index = int(selection[0])
            self.selected_index = index
            self.show_preview_on_canvas(index)
        else:
            self.selected_index = -1
            self.preview_canvas.delete('all')
            self.preview_info.config(text="请选择图片进行预览")

    def show_preview_on_canvas(self, index):
        """在画布上显示预览"""
        if index < 0 or index >= len(self.image_files):
            return

        try:
            image_path = self.image_files[index]
            image = Image.open(image_path)
            image = ImageOps.exif_transpose(image)
            
            # 简单预览原图，或者如果性能允许，预览带水印效果（这里先预览原图+提示）
            # 计算缩放
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                image.thumbnail((canvas_width - 10, canvas_height - 10), Image.Resampling.LANCZOS)
                
            photo = ImageTk.PhotoImage(image)
            self.preview_canvas.delete('all')
            self.preview_canvas.create_image(canvas_width//2, canvas_height//2, image=photo)
            self.preview_canvas.image = photo
            
            filename = os.path.basename(image_path)
            self.preview_info.config(text=f"预览: {filename} (点击'预览水印'查看效果)")
            
        except Exception as e:
            self.logger.error(f"预览失败: {e}")

    def rgb_to_hex(self, rgb):
        """RGB颜色转十六进制"""
        return '#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])

    def hex_to_rgb(self, hex_color):
        """十六进制颜色转RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def get_contrast_color(self, rgb):
        """获取对比色"""
        # 计算亮度
        luminance = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
        return 'white' if luminance < 128 else 'black'

    def choose_color(self):
        """选择颜色"""
        color = colorchooser.askcolor(
            initialcolor=self.rgb_to_hex(self.watermark_color),
            title="选择水印颜色"
        )
        if color[1]:
            self.watermark_color = list(map(int, color[0]))
            self.color_button.config(
                bg=color[1],
                fg=self.get_contrast_color(self.watermark_color)
            )

    @handle_exception
    def select_folder(self):
        """选择文件夹"""
        folder_path = filedialog.askdirectory(title="选择包含图片的文件夹")
        if folder_path:
            self.current_folder.set(folder_path)
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
        self.update_file_info()

        if self.image_files:
            self.message_queue.put({
                'type': 'status',
                'data': f"已加载 {len(self.image_files)} 个图片文件"
            })
            self.update_image_list()

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
    def preview_watermark(self):
        """预览水印效果"""
        if self.selected_index >= 0:
             # 优先使用列表中选中的图片
             try:
                 image_path = self.image_files[self.selected_index]
                 self.show_watermark_preview(image_path)
                 return
             except Exception:
                 pass

        if not self.image_files:
            messagebox.showwarning("警告", "请先选择图片文件夹")
            return

        try:
            # 使用第一张图片进行预览
            image_path = self.image_files[0]
            self.show_watermark_preview(image_path)

        except Exception as e:
            self.logger.error(f"预览失败: {e}")
            messagebox.showerror("错误", f"预览失败: {e}")

    def show_watermark_preview(self, image_path):
        """显示水印预览窗口"""
        try:
            # 加载图片
            image = Image.open(image_path)
            image = ImageOps.exif_transpose(image)

            # 处理水印文本
            text = self.process_dynamic_text(self.watermark_text.get(), image)

            # 创建水印
            watermarked = self.add_watermark_to_image(image, text)

            # 显示预览窗口
            self.show_preview_window(watermarked, os.path.basename(image_path))

        except Exception as e:
            self.logger.error(f"创建预览失败: {e}")
            raise

    def process_dynamic_text(self, text, image):
        """处理动态文本占位符"""
        if "{exif_date}" in text:
            exif_date = get_exif_datetime(image)
            replace_text = exif_date if exif_date else "N/A"
            text = text.replace("{exif_date}", replace_text)
        return text

    def add_watermark_to_image(self, image, text):
        """为图片添加水印"""
        # 转换为RGBA
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        # 创建水印层
        watermark = Image.new('RGBA', image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark)

        # 计算字体大小
        if self.multi_size_var.get():
            font_size = self.calculate_adaptive_font_size(text, image.size)
        else:
            font_size = self.font_size.get()

        # 获取字体
        font = self.get_font(text, font_size)

        # 计算文本尺寸
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 计算位置
        x, y = self.calculate_position(image.size, (text_width, text_height))

        # 确定颜色
        color = self.watermark_color
        if self.high_contrast_var.get():
            color = self.calculate_contrast_color_for_region(image, x, y, text_width, text_height)

        # 绘制水印
        opacity_value = int(self.opacity.get() * 255 / 100)
        fill_color = (*color, opacity_value)

        draw.text((x, y), text, font=font, fill=fill_color)

        # 合成图片
        result = Image.alpha_composite(image, watermark)
        return result

    def calculate_adaptive_font_size(self, text, image_size):
        """计算自适应字体大小"""
        img_w, img_h = image_size
        base_size = self.font_size.get()

        # 目标宽度为图片宽度的80%
        target_width = img_w * 0.8
        min_size = max(10, int(min(img_w, img_h) * 0.02))
        max_size = int(min(img_w, img_h) * 0.3)

        # 二分查找最佳字体大小
        best_size = min_size
        low, high = min_size, max_size

        # Create a single temporary image and draw object for measurement
        temp_img = Image.new('RGB', (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)

        for _ in range(10):  # 最多迭代10次
            if low > high:
                break

            mid = (low + high) // 2
            font = self.get_font(text, mid)

            bbox = temp_draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]

            if text_width <= target_width:
                best_size = mid
                low = mid + 1
            else:
                high = mid - 1

        return max(min_size, min(best_size, max_size))

    def get_font(self, text, size):
        """获取合适的字体"""
        try:
            if contains_chinese(text):
                return ImageFont.truetype(self.font_chinese, max(1, size))
            else:
                return ImageFont.truetype(self.font_english, max(1, size))
        except:
            return ImageFont.load_default()

    def calculate_position(self, image_size, text_size):
        """计算水印位置"""
        img_w, img_h = image_size
        text_w, text_h = text_size
        margin = 10

        position = self.position_var.get()
        if position == "左上角":
            return margin, margin
        elif position == "右上角":
            return img_w - text_w - margin, margin
        elif position == "左下角":
            return margin, img_h - text_h - margin
        elif position == "右下角":
            return img_w - text_w - margin, img_h - text_h - margin
        elif position == "中心":
            return (img_w - text_w) // 2, (img_h - text_h) // 2
        else:
            return margin, margin

    def calculate_contrast_color_for_region(self, image, x, y, width, height):
        """计算区域对比色"""
        try:
            # 裁剪区域
            region = image.crop((x, y, x + width, y + height))
            # 转换为RGB计算平均颜色
            if region.mode != 'RGB':
                region = region.convert('RGB')

            stat = ImageStat.Stat(region)
            mean = stat.mean

            # 计算亮度
            luminance = 0.299 * mean[0] + 0.587 * mean[1] + 0.114 * mean[2]

            # 返回对比色
            return (0, 0, 0) if luminance > 128 else (255, 255, 255)

        except Exception:
            return self.watermark_color

    def show_preview_window(self, image, title):
        """显示预览窗口"""
        preview_window = tk.Toplevel(self.parent_frame)
        preview_window.title(f"水印预览 - {title}")
        preview_window.geometry("800x600")
        preview_window.resizable(True, True)

        # 调整图片大小以适应窗口
        max_width, max_height = 780, 580
        image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        # 转换为PhotoImage
        photo = ImageTk.PhotoImage(image)

        # 显示图片
        label = ttk.Label(preview_window, image=photo)
        label.image = photo
        label.pack(expand=True, padx=10, pady=10)

    @handle_exception
    def start_processing(self):
        """开始处理"""
        if not self.image_files:
            messagebox.showwarning("警告", "请先选择图片文件夹")
            return

        text = self.watermark_text.get().strip()
        if not text:
            messagebox.showwarning("警告", "请输入水印文本")
            return

        # 保存设置
        self.save_settings()

        # 禁用控件
        self.process_btn.config(state='disabled')
        self.stop_btn.config(state='normal')

        # 启动处理线程
        self.is_processing = True
        self.stop_requested = False

        thread = threading.Thread(target=self.process_images_thread, daemon=True)
        thread.start()

    def process_images_thread(self):
        """处理图片的线程函数"""
        try:
            # 创建输出文件夹
            output_folder = create_output_folder(self.current_folder.get(), "Watermarked_Images")

            text = self.watermark_text.get().strip()
            total_images = len(self.image_files)
            processed_count = 0
            error_count = 0

            self.message_queue.put({
                'type': 'status',
                'data': "开始批量添加水印..."
            })

            for i, image_path in enumerate(self.image_files):
                if self.stop_requested:
                    break

                # 更新进度
                progress = (i + 1) / total_images * 100
                self.message_queue.put({
                    'type': 'progress',
                    'data': progress
                })

                filename = os.path.basename(image_path)
                self.message_queue.put({
                    'type': 'status',
                    'data': f"处理图片 {i+1}/{total_images}: {filename}"
                })

                try:
                    # 处理图片
                    image = Image.open(image_path)
                    image = ImageOps.exif_transpose(image)

                    # 处理动态文本
                    processed_text = self.process_dynamic_text(text, image)

                    # 添加水印
                    watermarked = self.add_watermark_to_image(image, processed_text)

                    # 保存文件
                    output_path = os.path.join(output_folder, filename)
                    self.save_image(watermarked, output_path, image.format)

                    processed_count += 1

                except Exception as e:
                    error_count += 1
                    self.logger.error(f"处理图片失败 {image_path}: {e}")

            # 完成
            if self.stop_requested:
                self.message_queue.put({
                    'type': 'status',
                    'data': "处理已取消"
                })
            else:
                self.message_queue.put({
                    'type': 'status',
                    'data': f"处理完成 - 成功: {processed_count}, 失败: {error_count}"
                })

                if processed_count > 0:
                    self.message_queue.put({
                        'type': 'info',
                        'data': f"水印图片已保存到:\n{output_folder}"
                    })

                    # 询问是否打开文件夹
                    # self.open_output_folder(output_folder) # 用户反馈：不需要自动打开

        except Exception as e:
            self.logger.error(f"批量处理失败: {e}")
            self.message_queue.put({
                'type': 'error',
                'data': f"批量处理失败: {e}"
            })

        finally:
            # 恢复控件状态
            self.is_processing = False
            self.message_queue.put({
                'type': 'enable_controls',
                'data': True
            })

    def save_image(self, image, output_path, original_format):
        """保存图片"""
        try:
            # Prepare format
            save_format = original_format if original_format else 'PNG'
            
            # Handle JPEG specifics
            if save_format.upper() in ('JPEG', 'JPG'):
                # JPEG supports no alpha, convert to RGB if needed
                if image.mode == 'RGBA':
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    background.paste(image, mask=image.split()[-1])
                    image = background
                image.save(output_path, 'JPEG', quality=95)
            
            # Handle other formats
            elif save_format.upper() == 'PNG':
                image.save(output_path, 'PNG')
            elif save_format.upper() == 'WEBP':
                image.save(output_path, 'WEBP')
            else:
                # Fallback for unknown formats, try to save as is or default to PNG if it fails
                try:
                    image.save(output_path, save_format)
                except:
                    # If saving with original format fails (e.g. BMP with alpha), fall back to PNG
                    if not output_path.lower().endswith('.png'):
                        output_path = os.path.splitext(output_path)[0] + '.png'
                    image.save(output_path, 'PNG')

        except Exception as e:
            self.logger.error(f"保存图片失败 {output_path}: {e}")
            raise

    def stop_processing(self):
        """停止处理"""
        self.stop_requested = True
        self.message_queue.put({
            'type': 'status',
            'data': "正在停止处理..."
        })

    def open_output_folder(self, folder_path):
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

    def enable_controls(self, enable=True):
        """启用/禁用控件"""
        if enable:
            self.process_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
        else:
            self.process_btn.config(state='disabled')
            self.stop_btn.config(state='normal')

    def load_settings(self):
        """加载设置"""
        try:
            watermark_config = self.config_manager.get_section('watermark')

            self.watermark_text.set(watermark_config.get('text', 'MU Group Leo: +86 13819858718'))
            self.font_size.set(watermark_config.get('font_size', 40))
            self.opacity.set(watermark_config.get('opacity', 80))
            self.watermark_color = watermark_config.get('color', [255, 255, 0])
            self.position_var.set(watermark_config.get('position', '中心'))
            self.multi_size_var.set(watermark_config.get('multi_size', True))
            self.high_contrast_var.set(watermark_config.get('high_contrast', True))

            # 更新颜色按钮
            self.color_button.config(
                bg=self.rgb_to_hex(self.watermark_color),
                fg=self.get_contrast_color(self.watermark_color)
            )

            self.opacity_label.config(text=f"{self.opacity.get()}%")

        except Exception as e:
            self.logger.error(f"加载设置失败: {e}")

    def save_settings(self):
        """保存设置"""
        try:
            watermark_settings = {
                'text': self.watermark_text.get(),
                'font_size': self.font_size.get(),
                'opacity': self.opacity.get(),
                'color': self.watermark_color,
                'position': self.position_var.get(),
                'multi_size': self.multi_size_var.get(),
                'high_contrast': self.high_contrast_var.get()
            }

            self.config_manager.update_section('watermark', watermark_settings)

        except Exception as e:
            self.logger.error(f"保存设置失败: {e}")