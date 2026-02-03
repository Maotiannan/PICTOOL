#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF转换器模块
基于原始pic2pdf项目重构，支持图片转PDF功能
"""

import os
import sys
import time
import threading
import queue
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any

try:
    import img2pdf
except ImportError:
    img2pdf = None

from utils import (
    get_image_files, is_image_file, format_file_size,
    create_output_folder, safe_filename, handle_exception,
    get_exif_datetime
)

class PdfConverter:
    """PDF转换器主类"""

    def __init__(self, parent_frame: ttk.Frame, config_manager,
                 message_queue: queue.Queue, status_callback: Callable):
        self.parent_frame = parent_frame
        self.config_manager = config_manager
        self.message_queue = message_queue
        self.status_callback = status_callback

        self.logger = logging.getLogger("PdfConverter")

        # 状态变量
        self.image_files = []
        self.current_folder = tk.StringVar()
        self.pdf_name = tk.StringVar(value="图片文档")
        self.is_processing = False
        self.stop_requested = False

        # PDF参数变量
        self.quality_var = tk.IntVar(value=95)
        self.page_size_var = tk.StringVar(value="A4")
        self.orientation_var = tk.StringVar(value="portrait")
        self.margin_var = tk.IntVar(value=10)

        # 选中项
        self.selected_index = -1
        self.selected_images = []

        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        """设置用户界面"""
        # 主容器
        main_container = ttk.Frame(self.parent_frame)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)

        # 顶部：PDF设置
        top_frame = ttk.LabelFrame(main_container, text="PDF设置", padding=10)
        top_frame.pack(fill='x', pady=(0, 10))

        self.create_pdf_settings_panel(top_frame)

        # 底部：控制按钮
        control_frame = ttk.Frame(main_container)
        control_frame.pack(fill='x', side='bottom', pady=10)

        self.create_control_panel(control_frame)

        # 中间：文件选择和列表
        middle_frame = ttk.Frame(main_container)
        middle_frame.pack(fill='both', expand=True, pady=(0, 10))

        # 左侧：文件选择
        left_frame = ttk.Frame(middle_frame)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))

        self.create_file_selection_panel(left_frame)

        # 右侧：预览
        right_frame = ttk.LabelFrame(middle_frame, text="图片预览", padding=10, width=300)
        right_frame.pack(side='right', fill='y')
        right_frame.pack_propagate(False)

        self.create_preview_panel(right_frame)

    def create_pdf_settings_panel(self, parent):
        """创建PDF设置面板"""
        # PDF名称
        name_frame = ttk.Frame(parent)
        name_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(name_frame, text="PDF文件名:").pack(side='left')
        ttk.Entry(name_frame, textvariable=self.pdf_name, width=30).pack(side='left', padx=(5, 0))

        # 页面设置
        page_frame = ttk.Frame(parent)
        page_frame.pack(fill='x', pady=(0, 10))

        # 页面大小
        ttk.Label(page_frame, text="页面大小:").pack(side='left')
        page_size_combo = ttk.Combobox(
            page_frame,
            textvariable=self.page_size_var,
            values=['A4', 'A3', 'A5', 'Letter', 'Legal'],
            state='readonly',
            width=10
        )
        page_size_combo.pack(side='left', padx=(5, 20))

        # 页面方向
        ttk.Label(page_frame, text="页面方向:").pack(side='left')
        orientation_combo = ttk.Combobox(
            page_frame,
            textvariable=self.orientation_var,
            values=['portrait', 'landscape'],
            state='readonly',
            width=12
        )
        orientation_combo.pack(side='left', padx=(5, 0))

        # 质量和边距
        quality_frame = ttk.Frame(parent)
        quality_frame.pack(fill='x')

        # 质量
        ttk.Label(quality_frame, text="图片质量:").pack(side='left')
        quality_scale = ttk.Scale(
            quality_frame,
            from_=10,
            to=100,
            variable=self.quality_var,
            orient='horizontal',
            length=150
        )
        quality_scale.pack(side='left', padx=(5, 10))

        self.quality_label = ttk.Label(quality_frame, text="95%")
        self.quality_label.pack(side='left', padx=(0, 20))

        # 边距
        ttk.Label(quality_frame, text="页边距:").pack(side='left')
        margin_spinbox = ttk.Spinbox(
            quality_frame,
            from_=0,
            to=50,
            textvariable=self.margin_var,
            width=8
        )
        margin_spinbox.pack(side='left', padx=(5, 0))
        ttk.Label(quality_frame, text="mm").pack(side='left')

        quality_scale.config(command=lambda v: self.quality_label.config(text=f"{int(float(v))}%"))

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

        # 文件列表
        list_frame = ttk.LabelFrame(parent, text="图片列表 (可拖拽排序)", padding=10)
        list_frame.pack(fill='both', expand=True)

        # 创建Treeview
        columns = ('文件名', '尺寸', '大小')
        self.image_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        # 设置列标题
        self.image_tree.heading('文件名', text='文件名')
        self.image_tree.heading('尺寸', text='尺寸')
        self.image_tree.heading('大小', text='大小')

        # 设置列宽
        self.image_tree.column('文件名', width=200)
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
        self.image_tree.bind('<Button-3>', self.show_context_menu)

        # 控制按钮
        control_frame = ttk.Frame(list_frame)
        control_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(5, 0))

        ttk.Button(control_frame, text="上移", command=self.move_up).pack(side='left', padx=(0, 5))
        ttk.Button(control_frame, text="下移", command=self.move_down).pack(side='left', padx=(0, 5))
        ttk.Button(control_frame, text="删除", command=self.remove_selected).pack(side='left', padx=(0, 5))
        ttk.Button(control_frame, text="清空", command=self.clear_all).pack(side='left')

    def create_preview_panel(self, parent):
        """创建预览面板"""
        # 预览画布
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill='both', expand=True)

        self.preview_canvas = tk.Canvas(canvas_frame, bg='white')
        self.preview_canvas.pack(fill='both', expand=True)

        # 信息标签
        self.preview_info = ttk.Label(parent, text="请选择图片进行预览", foreground='gray')
        self.preview_info.pack(pady=5)

    def create_control_panel(self, parent):
        """创建控制面板"""
        # 生成按钮
        self.generate_btn = ttk.Button(
            parent,
            text="生成PDF",
            command=self.start_generation,
            style='Success.TButton'
        )
        self.generate_btn.pack(side='left', padx=(0, 10))

        # 停止按钮
        self.stop_btn = ttk.Button(
            parent,
            text="停止生成",
            command=self.stop_generation,
            state='disabled',
            style='Danger.TButton'
        )
        self.stop_btn.pack(side='left', padx=(0, 10))

        # 文件信息
        self.file_count_label = ttk.Label(parent, text="未选择图片")
        self.file_count_label.pack(side='right')

    def show_context_menu(self, event):
        """显示右键菜单"""
        # 选中项
        item = self.image_tree.identify_row(event.y)
        if item:
            self.image_tree.selection_set(item)

            # 创建菜单
            context_menu = tk.Menu(self.parent_frame, tearoff=0)
            context_menu.add_command(label="删除", command=self.remove_selected)
            context_menu.add_command(label="上移", command=self.move_up)
            context_menu.add_command(label="下移", command=self.move_down)
            context_menu.add_separator()
            context_menu.add_command(label="在文件管理器中显示", command=self.show_in_explorer)

            context_menu.post(event.x_root, event.y_root)

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
        self.update_image_list()
        self.update_file_info()

        if self.image_files:
            self.message_queue.put({
                'type': 'status',
                'data': f"已加载 {len(self.image_files)} 个图片文件"
            })

    def update_image_list(self):
        """更新图片列表"""
        # 清空现有项目
        for item in self.image_tree.get_children():
            self.image_tree.delete(item)

        # 先添加文件名，尺寸显示"加载中..."
        for i, image_path in enumerate(self.image_files):
            filename = os.path.basename(image_path)
            self.image_tree.insert('', 'end', iid=str(i), values=(filename, "加载中...", "加载中..."))

        # 启动后台线程加载详细信息
        threading.Thread(target=self._load_image_details_thread, daemon=True).start()

    def _load_image_details_thread(self):
        """后台加载图片详细信息"""
        for i, image_path in enumerate(self.image_files):
            try:
                if not os.path.exists(image_path):
                    continue

                # 获取文件大小
                file_size = format_file_size(os.path.getsize(image_path))
                
                # 获取图片尺寸（尽量不完全加载图片以节省内存）
                with Image.open(image_path) as img:
                     size_text = f"{img.width}×{img.height}"

                # 更新界面（需在主线程执行）
                self.parent_frame.after(0, self._update_tree_item, str(i), size_text, file_size)

            except Exception as e:
                self.logger.error(f"读取图片信息失败 {image_path}: {e}")
                self.parent_frame.after(0, self._update_tree_item, str(i), "未知", "未知")
    
    def _update_tree_item(self, item_id, size_text, file_size):
        """更新单个列表项"""
        if self.image_tree.exists(item_id):
            current_values = self.image_tree.item(item_id)['values']
            if current_values:
                 self.image_tree.item(item_id, values=(current_values[0], size_text, file_size))

    def update_file_info(self):
        """更新文件信息"""
        count = len(self.image_files)
        if count > 0:
            total_size = sum(os.path.getsize(f) for f in self.image_files if os.path.exists(f))
            size_text = format_file_size(total_size)
            self.file_count_label.config(text=f"共 {count} 个图片 (总大小: {size_text})")
        else:
            self.file_count_label.config(text="未选择图片")

    def on_tree_select(self, event):
        """树形控件选择事件"""
        selection = self.image_tree.selection()
        if selection:
            index = self.image_tree.index(selection[0])
            self.selected_index = index
            self.show_preview(index)
        else:
            self.selected_index = -1
            self.clear_preview()

    def show_preview(self, index: int):
        """显示图片预览"""
        if index < 0 or index >= len(self.image_files):
            return

        try:
            image_path = self.image_files[index]
            image = Image.open(image_path)

            # 调整图片大小以适应预览区域
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()

            if canvas_width > 1 and canvas_height > 1:
                image.thumbnail((canvas_width - 20, canvas_height - 20), Image.Resampling.LANCZOS)

            # 转换为PhotoImage
            photo = ImageTk.PhotoImage(image)

            # 清空画布并显示图片
            self.preview_canvas.delete('all')
            x = (canvas_width - image.width) // 2
            y = (canvas_height - image.height) // 2
            self.preview_canvas.create_image(x, y, anchor='nw', image=photo)
            self.preview_canvas.image = photo  # 保持引用

            # 更新信息
            filename = os.path.basename(image_path)
            info_text = f"{filename}\n尺寸: {image.width}×{image.height}"
            self.preview_info.config(text=info_text)

        except Exception as e:
            self.logger.error(f"显示预览失败: {e}")
            self.preview_info.config(text="预览失败")

    def clear_preview(self):
        """清空预览"""
        self.preview_canvas.delete('all')
        self.preview_info.config(text="请选择图片进行预览")

    def move_up(self):
        """上移选中的图片"""
        if self.selected_index <= 0:
            return

        # 交换位置
        self.image_files[self.selected_index - 1], self.image_files[self.selected_index] = \
            self.image_files[self.selected_index], self.image_files[self.selected_index - 1]

        # 更新列表
        self.update_image_list()

        # 重新选择
        self.selected_index -= 1
        if self.selected_index >= 0:
            item = self.image_tree.get_children()[self.selected_index]
            self.image_tree.selection_set(item)
            self.image_tree.see(item)

    def move_down(self):
        """下移选中的图片"""
        if self.selected_index < 0 or self.selected_index >= len(self.image_files) - 1:
            return

        # 交换位置
        self.image_files[self.selected_index], self.image_files[self.selected_index + 1] = \
            self.image_files[self.selected_index + 1], self.image_files[self.selected_index]

        # 更新列表
        self.update_image_list()

        # 重新选择
        self.selected_index += 1
        if self.selected_index < len(self.image_files):
            item = self.image_tree.get_children()[self.selected_index]
            self.image_tree.selection_set(item)
            self.image_tree.see(item)

    def remove_selected(self):
        """删除选中的图片"""
        if self.selected_index < 0 or self.selected_index >= len(self.image_files):
            return

        # 删除文件
        del self.image_files[self.selected_index]

        # 更新列表
        self.update_image_list()
        self.update_file_info()

        # 清空预览
        self.clear_preview()
        self.selected_index = -1

    def clear_all(self):
        """清空所有图片"""
        if not self.image_files:
            return

        if messagebox.askyesno("确认", "确定要清空所有图片吗？"):
            self.image_files = []
            self.update_image_list()
            self.update_file_info()
            self.clear_preview()
            self.selected_index = -1

    def show_in_explorer(self):
        """在文件管理器中显示选中的文件"""
        if self.selected_index < 0 or self.selected_index >= len(self.image_files):
            return

        file_path = self.image_files[self.selected_index]
        try:
            if sys.platform == "win32":
                os.startfile(f'explorer /select,"{file_path}"')
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(['open', '-R', file_path])
            else:
                import subprocess
                subprocess.run(['xdg-open', os.path.dirname(file_path)])
        except Exception as e:
            self.logger.error(f"打开文件管理器失败: {e}")

    @handle_exception
    def start_generation(self):
        """开始生成PDF"""
        if not self.image_files:
            messagebox.showwarning("警告", "请先选择图片文件夹")
            return

        pdf_name = self.pdf_name.get().strip()
        if not pdf_name:
            messagebox.showwarning("警告", "请输入PDF文件名")
            return

        # 检查img2pdf库
        if img2pdf is None:
            messagebox.showerror(
                "错误",
                "缺少img2pdf库，无法生成PDF。\n请运行: pip install img2pdf"
            )
            return

        # 保存当前设置
        self.save_settings()

        # 禁用控件
        self.generate_btn.config(state='disabled')
        self.stop_btn.config(state='normal')

        # 启动处理线程
        self.is_processing = True
        self.stop_requested = False

        thread = threading.Thread(target=self.generate_pdf_thread, daemon=True)
        thread.start()

    def generate_pdf_thread(self):
        """生成PDF的线程函数"""
        try:
            # 获取输出路径
            output_folder = create_output_folder(self.current_folder.get(), "_pdf")
            today = datetime.now().strftime("%Y%m%d")
            pdf_name = self.pdf_name.get().strip()
            output_filename = f"{pdf_name} {today}.pdf"
            output_path = os.path.join(output_folder, output_filename)

            self.message_queue.put({
                'type': 'status',
                'data': "开始生成PDF..."
            })

            # 获取参数
            quality = self.quality_var.get()
            
            # 准备图片数据
            pdf_bytes = []
            total_images = len(self.image_files)
            
            import io
            
            for i, image_path in enumerate(self.image_files):
                if self.stop_requested:
                    raise Exception("用户停止")

                self.message_queue.put({
                    'type': 'status',
                    'data': f"正在处理图片 ({i+1}/{total_images}): {os.path.basename(image_path)}"
                })
                self.message_queue.put({
                    'type': 'progress',
                    'data': (i / total_images) * 90  # 预留10%给PDF生成
                })

                try:
                    with Image.open(image_path) as img:
                        # 转换Exif方向
                        from PIL import ImageOps
                        img = ImageOps.exif_transpose(img)
                        
                        # 如果需要压缩（质量<100），则转换为JPEG
                        # 注意：如有透明通道需预处理
                        if img.mode == 'RGBA':
                            background = Image.new('RGB', img.size, (255, 255, 255))
                            background.paste(img, mask=img.split()[-1])
                            img = background
                        elif img.mode != 'RGB':
                            img = img.convert('RGB')
                            
                        # 保存到内存
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='JPEG', quality=quality)
                        pdf_bytes.append(img_byte_arr.getvalue())
                        
                except Exception as e:
                    self.logger.error(f"处理图片失败 {image_path}: {e}")
                    # 如果处理失败，尝试直接读取原文件（作为后备）
                    with open(image_path, "rb") as f:
                         pdf_bytes.append(f.read())

            self.message_queue.put({
                'type': 'status',
                'data': "正在合成PDF文件..."
            })

            # 生成PDF
            with open(output_path, "wb") as f:
                f.write(img2pdf.convert(pdf_bytes))

            # 完成
            self.message_queue.put({
                'type': 'progress',
                'data': 100
            })
            
            self.message_queue.put({
                'type': 'status',
                'data': f"PDF生成完成: {output_filename}"
            })

            self.message_queue.put({
                'type': 'info',
                'data': f"PDF文件已保存到:\n{output_path}"
            })

            # 询问是否打开文件夹
            # self.open_output_folder(output_folder)

        except Exception as e:
            self.logger.error(f"生成PDF失败: {e}")
            self.message_queue.put({
                'type': 'error',
                'data': f"生成PDF失败: {e}"
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
            pdf_config = self.config_manager.get_section('pdf')

            self.quality_var.set(pdf_config.get('quality', 95))
            self.page_size_var.set(pdf_config.get('page_size', 'A4'))
            self.orientation_var.set(pdf_config.get('orientation', 'portrait'))
            self.margin_var.set(pdf_config.get('margin', 10))

            self.quality_label.config(text=f"{self.quality_var.get()}%")

        except Exception as e:
            self.logger.error(f"加载设置失败: {e}")

    def save_settings(self):
        """保存设置"""
        try:
            pdf_settings = {
                'quality': self.quality_var.get(),
                'page_size': self.page_size_var.get(),
                'orientation': self.orientation_var.get(),
                'margin': self.margin_var.get()
            }

            self.config_manager.update_section('pdf', pdf_settings)

        except Exception as e:
            self.logger.error(f"保存设置失败: {e}")