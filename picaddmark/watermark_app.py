# --- START OF FILE watermark_app.py ---

import os
import json
import webbrowser
import sys
import logging # 导入 logging 模块
import traceback
import threading # 导入线程模块
import queue     # 导入队列模块
from datetime import datetime
from tkinter import Tk, Label, Button, Entry, filedialog, messagebox, colorchooser
from tkinter import ttk, StringVar, Text, Scrollbar
import tkinter.scrolledtext as scrolledtext
# Pillow (PIL Fork) 用于图像处理
from PIL import Image, ImageDraw, ImageFont, ImageOps, ExifTags, ImageStat

# --- 配置 & 日志设置 ---
def setup_logging():
    """配置日志系统（控制台和GUI）, 返回根记录器"""
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger_instance = logging.getLogger('watermark_app')
    logger_instance.setLevel(logging.INFO) # 设置最低日志级别

    # 确保只添加一次处理器
    if not logger_instance.handlers:
        # 控制台处理器
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(log_formatter)
        logger_instance.addHandler(stream_handler)

    return logger_instance

# --- 自定义日志处理器，用于 Tkinter Text 控件 ---
class TextHandler(logging.Handler):
    """将日志消息定向到 Tkinter Text 控件的日志处理器。"""
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append_message():
            # 安全地在主线程中更新Text控件
            current_state = self.text_widget.cget('state')
            self.text_widget.config(state='normal')
            self.text_widget.insert('end', msg + '\n')
            self.text_widget.config(state=current_state)
            self.text_widget.see('end') # 滚动到底部
        # 使用 after(0, ...) 将 GUI 更新安排到 Tkinter 主事件循环中执行
        self.text_widget.after(0, append_message)

# --- 全局日志设置 ---
logger = setup_logging() # 设置控制台和准备GUI日志

# --- 获取资源路径 (用于 PyInstaller 打包) ---
def get_resource_path(relative_path):
    """获取资源文件的绝对路径 (用于 PyInstaller 打包后寻找资源)"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- 判断字符是否为中文 ---
def is_chinese(char):
    """判断一个字符是否是中文字符 (基于 Unicode 范围)"""
    return '\u4e00' <= char <= '\u9fff'

# --- EXIF 标签字典 ---
TAGS = {v: k for k, v in ExifTags.TAGS.items()}

# --- WatermarkApp 类 ---
class WatermarkApp:
    def __init__(self, master):
        self.master = master
        master.title("批量图片加水印") # 设置窗口标题

        self.font_chinese = None
        self.font_english = None
        self.init_fonts()

        # --- GUI 控件设置 ---
        # 第 0 行: 水印文本输入 和 帮助图标
        self.label_text = Label(master, text="输入水印内容：")
        self.label_text.grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.entry_text = Entry(master, width=50)
        self.entry_text.grid(row=0, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        self.help_icon_label = Label(master, text="?", fg="blue", cursor="question_arrow")
        self.help_icon_label.grid(row=0, column=3, sticky="w", padx=(0, 10))
        self.help_icon_label.bind("<Button-1>", self.show_exif_help)

        # 第 1 行: 字体大小 & 多尺寸适配
        self.label_font_size = Label(master, text="输入基础字体大小：")
        self.label_font_size.grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.entry_font_size = Entry(master, width=10)
        self.entry_font_size.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        self.multi_size_var = StringVar(value="0")
        self.multi_size_check = ttk.Checkbutton(master, text="多尺寸适配 (自动调整字体大小)", variable=self.multi_size_var)
        self.multi_size_check.grid(row=1, column=2, padx=10, pady=5, sticky="w")

        # 第 2 行: 透明度
        self.label_opacity = Label(master, text="输入透明度 (0-100)：")
        self.label_opacity.grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.entry_opacity = Entry(master, width=10)
        self.entry_opacity.grid(row=2, column=1, padx=10, pady=5, sticky="w")

        # 第 3 行: 颜色选择 & 高对比度模式
        self.label_color = Label(master, text="选择水印颜色：")
        self.label_color.grid(row=3, column=0, sticky="w", padx=10, pady=5)
        self.color_button = Button(master, text="选择颜色", command=self.choose_color)
        self.color_button.grid(row=3, column=1, padx=10, pady=5, sticky="w")
        self.color = (255, 255, 0)
        self.high_contrast_var = StringVar(value="0")
        self.high_contrast_check = ttk.Checkbutton(master, text="高对比度模式", variable=self.high_contrast_var)
        self.high_contrast_check.grid(row=3, column=2, padx=10, pady=5, sticky="w")

        # 第 4 行: 水印位置
        self.label_position = Label(master, text="选择水印位置：")
        self.label_position.grid(row=4, column=0, sticky="w", padx=10, pady=5)
        self.position_var = StringVar(value="右下角")
        self.position_options = ["左上角", "右上角", "左下角", "右下角", "中心"]
        self.position_dropdown = ttk.Combobox(master, textvariable=self.position_var, values=self.position_options, state="readonly", width=10)
        self.position_dropdown.grid(row=4, column=1, padx=10, pady=5, sticky="w")

        # 第 5 行: 文件夹选择 & 预览
        self.label_folder = Label(master, text="选择包含图片的文件夹:", justify="left", wraplength=350)
        self.label_folder.grid(row=5, column=0, sticky="nw", padx=10, pady=(10, 5))
        self.select_button = Button(master, text="选择文件夹", command=self.select_folder)
        self.select_button.grid(row=5, column=1, padx=10, pady=(10, 5), sticky="nw")
        self.preview_button = Button(master, text="预览水印", command=self.preview_watermark)
        self.preview_button.grid(row=5, column=2, padx=10, pady=(10, 5), sticky="nw")

        # 第 7 行: 进度条
        self.progress = ttk.Progressbar(master, orient="horizontal", length=400, mode="determinate")
        self.progress.grid(row=7, column=0, columnspan=4, padx=10, pady=5, sticky="ew")

        # 第 8 行: 进度标签
        self.progress_label = Label(master, text="")
        self.progress_label.grid(row=8, column=0, columnspan=4, padx=10, pady=(0, 10), sticky="ew")

        # --- 修改: 第 9 行: 处理按钮 和 停止按钮 ---
        self.process_button = Button(master, text="开始处理", command=self.start_processing_thread, state="disabled", bg="green", fg="white", width=15, font=("Arial", 12, "bold"), disabledforeground="grey")
        self.process_button.grid(row=9, column=0, columnspan=2, pady=5, sticky="e", padx=(0, 5)) # 放在左侧
        # --- 新增: 停止按钮 ---
        self.stop_button = Button(master, text="停止处理", command=self.request_stop_processing, state="disabled", bg="red", fg="white", width=15, font=("Arial", 12, "bold"), disabledforeground="grey")
        self.stop_button.grid(row=9, column=2, columnspan=2, pady=5, sticky="w", padx=(5, 0)) # 放在右侧

        # 第 10 行: 日志区域标签
        self.log_label = Label(master, text="日志输出:")
        self.log_label.grid(row=10, column=0, columnspan=4, sticky="w", padx=10, pady=(10, 0))
        # 第 11 行: 日志文本区域
        self.log_text_area = scrolledtext.ScrolledText(master, wrap='word', height=8, state='disabled',
                                                        borderwidth=1, relief="solid", font=("Consolas", 9))
        self.log_text_area.grid(row=11, column=0, columnspan=4, padx=10, pady=(0, 10), sticky="nsew")

        # 第 12 行: 保存 & 退出按钮
        self.save_button = Button(master, text="保存设置", command=self.save_settings)
        self.save_button.grid(row=12, column=0, padx=10, pady=5, sticky="w")
        self.exit_button = Button(master, text="退出", command=self.quit_app, width=15)
        self.exit_button.grid(row=12, column=3, padx=10, pady=5, sticky="e")

        self.selected_folder = ""
        self.output_folder = ""

        # --- 配置日志输出到 Text 控件 ---
        self.log_handler = TextHandler(self.log_text_area)
        log_formatter_gui = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(log_formatter_gui)
        self.log_handler.setLevel(logging.INFO)
        logger.addHandler(self.log_handler)

        # --- 线程和队列相关初始化 ---
        self.processing_queue = queue.Queue()
        self.processing_thread = None
        self.stop_requested = False # 新增: 停止标志

        # --- 最后设置 ---
        self.load_settings()
        self.entry_text.focus_set()

        # 配置行列权重以适应窗口缩放
        master.grid_columnconfigure(1, weight=1)
        master.grid_rowconfigure(11, weight=1)

    # --- 显示 EXIF 帮助信息的方法 ---
    def show_exif_help(self, event=None):
        """当点击问号图标时，显示 {exif_date} 的使用说明。"""
        help_text = """
您可以在水印内容中使用 {exif_date} 占位符。

程序在处理每张图片时，会尝试读取其 EXIF 信息中的拍摄日期和时间。

如果成功读取到日期时间（例如 "2023:10:27 15:30:00"），它会将其格式化为 "YYYY-MM-DD HH:MM:SS" (例如 "2023-10-27 15:30:00") 并替换掉 {exif_date}。

如果照片没有 EXIF 日期信息，或者无法读取，{exif_date} 会被替换为 "N/A"。
        """
        messagebox.showinfo("动态文本 {exif_date} 使用说明", help_text.strip())

    # --- 字体初始化 ---
    def init_fonts(self):
        """初始化字体, 优先使用 Arial (英文) 和 SimHei/SimSun (中文)"""
        logger.info("初始化字体...")
        try:
            english_fonts = ["arial.ttf", "Arial", "LiberationSans-Regular.ttf", "DejaVuSans.ttf", "times.ttf", "Times New Roman"]
            chinese_fonts = ["simhei.ttf", "SimHei", "msyh.ttc", "Microsoft YaHei", "simsun.ttc", "SimSun", "SourceHanSansSC-Regular.otf", "WenQuanYi Zen Hei.ttf"]

            self.font_english = None
            for font_name in english_fonts:
                try:
                    ImageFont.truetype(font_name, 12)
                    self.font_english = font_name
                    logger.info(f"成功加载英文字体: {font_name}")
                    break
                except IOError:
                    logger.debug(f"英文字体 {font_name} 未找到或无法加载.")
                except Exception as e:
                    logger.warning(f"加载英文字体 {font_name} 时发生其他错误: {e}")

            if self.font_english is None:
                logger.warning("未找到指定的英文字体 (如 Arial), 将使用 PIL 默认字体.")
                self.font_english = ImageFont.load_default()

            self.font_chinese = None
            for font_name in chinese_fonts:
                try:
                    ImageFont.truetype(font_name, 12)
                    self.font_chinese = font_name
                    logger.info(f"成功加载中文字体: {font_name}")
                    break
                except IOError:
                    logger.debug(f"中文字体 {font_name} 未找到或无法加载.")
                except Exception as e:
                    logger.warning(f"加载中文字体 {font_name} 时发生其他错误: {e}")

            if self.font_chinese is None:
                logger.warning("未找到指定的中文字体 (如 SimHei, SimSun, Microsoft YaHei), 将使用 PIL 默认字体.")
                self.font_chinese = ImageFont.load_default()

        except Exception as e:
            logger.error(f"初始化字体过程中发生严重错误: {str(e)}")
            logger.error(traceback.format_exc())
            messagebox.showwarning("字体加载警告", f"无法加载系统字体，将使用默认字体。\n水印效果可能受影响。\n错误信息：{str(e)}")
            self.font_english = ImageFont.load_default()
            self.font_chinese = ImageFont.load_default()

    # --- 颜色选择 ---
    def choose_color(self):
        """打开颜色选择器让用户选择颜色"""
        color_code = colorchooser.askcolor(initialcolor=self.color, title="选择水印颜色")
        if color_code and color_code[0]:
            self.color = tuple(int(c) for c in color_code[0])
            logger.info(f"用户选择颜色: {self.color}")

    # --- 文件夹选择 ---
    def select_folder(self):
        """打开对话框让用户选择包含图片的文件夹"""
        folder = filedialog.askdirectory()
        if folder:
            self.selected_folder = folder
            self.process_button.config(state="normal") # 启用“开始处理”按钮
            self.label_folder.config(text=f"已选文件夹:\n{self.selected_folder}")
            logger.info(f"用户选择文件夹: {self.selected_folder}")
        else:
            if not self.selected_folder:
                 self.process_button.config(state="disabled")
            logger.info("用户取消选择文件夹")

    # --- 计算水印位置 ---
    def calculate_position(self, image_size, text_bbox, position):
        """根据图片尺寸、文本框尺寸和选择的位置计算水印左上角坐标 (x, y)"""
        img_w, img_h = image_size
        text_w, text_h = text_bbox[0], text_bbox[1]
        margin = 10 # 水印距离图片边缘的像素数

        if position == "左上角":
            pos = (margin, margin)
        elif position == "右上角":
            pos = (img_w - text_w - margin, margin)
        elif position == "左下角":
            pos = (margin, img_h - text_h - margin)
        elif position == "右下角":
            pos = (img_w - text_w - margin, img_h - text_h - margin)
        elif position == "中心":
            pos = ((img_w - text_w) // 2, (img_h - text_h) // 2)
        else:
            logger.warning(f"遇到未知位置 '{position}'，使用左上角作为默认值。")
            pos = (margin, margin)

        final_x = max(0, min(pos[0], img_w - text_w))
        final_y = max(0, min(pos[1], img_h - text_h))
        return (final_x, final_y)

    # --- 获取字体样式对象 ---
    def get_font_style(self, font_name_or_path, font_size):
        """根据字体名称/路径和大小获取 Pillow 的 ImageFont 对象"""
        try:
            if isinstance(font_name_or_path, ImageFont.FreeTypeFont) or \
               isinstance(font_name_or_path, ImageFont.ImageFont):
                if hasattr(font_name_or_path, 'size') and font_name_or_path.size != font_size and isinstance(font_name_or_path, ImageFont.FreeTypeFont):
                     logger.debug(f"重新加载字体 {font_name_or_path.path} 为大小 {font_size}")
                     return ImageFont.truetype(font_name_or_path.path, max(1, int(font_size)))
                return font_name_or_path
            elif font_name_or_path and isinstance(font_name_or_path, str):
                safe_font_size = max(1, int(font_size))
                return ImageFont.truetype(font_name_or_path, safe_font_size)
            else:
                 logger.error("字体名称/路径无效，使用 PIL 默认字体。")
                 return ImageFont.load_default()
        except IOError:
             logger.error(f"无法加载字体文件: {font_name_or_path}。使用 PIL 默认字体。")
             return ImageFont.load_default()
        except Exception as e:
            logger.error(f"加载字体 {font_name_or_path} (大小 {font_size}) 失败: {e}。使用 PIL 默认字体。")
            logger.error(traceback.format_exc())
            return ImageFont.load_default()

    # --- 获取 EXIF 日期时间 ---
    def _get_exif_datetime(self, image):
        """尝试从图片的 EXIF 数据中提取拍摄日期时间 (DateTimeOriginal 或 DateTime)"""
        try:
            exif_data = image.getexif()
            if not exif_data:
                logger.debug("未找到 EXIF 数据。")
                return None

            TAG_DATETIME_ORIGINAL = 36867 # 拍摄日期时间
            TAG_DATETIME = 306          # 文件修改日期时间 (备用)

            datetime_original = exif_data.get(TAG_DATETIME_ORIGINAL)
            if datetime_original and isinstance(datetime_original, str):
                 logger.debug(f"找到 DateTimeOriginal: {datetime_original}")
                 datetime_original = datetime_original.split('\x00')[0].strip()
                 for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                     try:
                         dt_obj = datetime.strptime(datetime_original, fmt)
                         return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                     except ValueError:
                         continue
                 logger.warning(f"DateTimeOriginal 格式无法识别: {datetime_original}, 将返回原始字符串。")
                 return datetime_original

            datetime_modified = exif_data.get(TAG_DATETIME)
            if datetime_modified and isinstance(datetime_modified, str):
                logger.debug(f"找到 DateTime (作为备用): {datetime_modified}")
                datetime_modified = datetime_modified.split('\x00')[0].strip()
                for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                     try:
                         dt_obj = datetime.strptime(datetime_modified, fmt)
                         return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                     except ValueError:
                         continue
                logger.warning(f"DateTime 格式无法识别: {datetime_modified}, 将返回原始字符串。")
                return datetime_modified

            logger.debug(f"未找到 DateTimeOriginal ({TAG_DATETIME_ORIGINAL}) 或 DateTime ({TAG_DATETIME}) 标签。")
            return None
        except AttributeError:
            logger.warning("此图像对象不支持 getexif()。无法获取 EXIF 日期。")
            return None
        except Exception as e:
            logger.error(f"读取 EXIF 日期时出错: {e}")
            logger.error(traceback.format_exc())
            return None

    # --- 处理动态文本占位符 ---
    def _process_dynamic_text(self, text, image_obj):
        """处理水印文本中的占位符，如 {exif_date}"""
        processed_text = text
        if "{exif_date}" in text:
            exif_date_str = self._get_exif_datetime(image_obj)
            replace_with = exif_date_str if exif_date_str else "N/A"
            logger.info(f"EXIF 日期查找结果: '{replace_with}' (用于替换 {{exif_date}})")
            processed_text = processed_text.replace("{exif_date}", replace_with)
        return processed_text

    # --- 计算高对比度颜色 ---
    def _calculate_contrast_color(self, image_region):
        """计算给定图像区域的平均颜色，并返回高对比度的颜色（黑或白）。"""
        try:
            if not image_region or image_region.size[0] == 0 or image_region.size[1] == 0:
                logger.warning("计算对比色：提供的图像区域无效或为空。返回默认黑色。")
                return (0, 0, 0)

            avg_color = ImageStat.Stat(image_region).mean
            r_mean, g_mean, b_mean = avg_color[:3]
            logger.debug(f"计算对比色：区域平均 RGB = ({r_mean:.1f}, {g_mean:.1f}, {b_mean:.1f})")

            luminance = 0.299 * r_mean + 0.587 * g_mean + 0.114 * b_mean
            logger.debug(f"计算对比色：区域感知亮度 = {luminance:.1f}")

            if luminance < 128:
                contrast_color = (255, 255, 255) # 背景暗，用白色
                logger.debug("计算对比色：背景较暗，选择白色。")
            else:
                contrast_color = (0, 0, 0) # 背景亮，用黑色
                logger.debug("计算对比色：背景较亮，选择黑色。")

            return contrast_color

        except Exception as e:
            logger.error(f"计算对比色时出错: {e}")
            logger.error(traceback.format_exc())
            return (0, 0, 0) # 出错时返回默认黑色

    # --- 预览水印 ---
    def preview_watermark(self):
        """在选定文件夹的第一张支持的图片上预览水印效果"""
        logger.info("开始预览水印...")
        if not self.selected_folder:
            messagebox.showwarning("未选择文件夹", "请先选择一个包含图片的文件夹！")
            logger.warning("预览请求：未选择文件夹。")
            return

        try:
            base_watermark_text, base_font_size, opacity_percent, position = self._get_validated_params()
            opacity_value = int(opacity_percent * 255 / 100)
            is_adaptive = self.multi_size_var.get() == "1"
            is_high_contrast = self.high_contrast_var.get() == "1"

            supported_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')
            image_files = [f for f in os.listdir(self.selected_folder)
                           if os.path.isfile(os.path.join(self.selected_folder, f)) and f.lower().endswith(supported_extensions)]
            if not image_files:
                messagebox.showwarning("无图片", "所选文件夹中未找到支持的图片格式。\n支持的格式: " + ", ".join(supported_extensions))
                logger.warning("预览请求：文件夹中无支持图片。")
                return

            preview_image_path = os.path.join(self.selected_folder, image_files[0])
            logger.info(f"使用图片进行预览: {preview_image_path}")

            try:
                original_image = Image.open(preview_image_path)
                try:
                    original_image = ImageOps.exif_transpose(original_image)
                    logger.debug("预览：已尝试根据 EXIF 修正图片方向。")
                except Exception as exif_err:
                    logger.warning(f"预览：尝试修正 EXIF 方向时出错: {exif_err}")

                img_w, img_h = original_image.size
                logger.debug(f"预览：原始图片尺寸: {img_w}x{img_h}")

                final_watermark_text = self._process_dynamic_text(base_watermark_text, original_image)
                logger.info(f"预览用最终水印文本: '{final_watermark_text}'")

                image_rgba = original_image.copy().convert("RGBA")

            except Exception as open_err:
                 messagebox.showerror("图片打开错误", f"无法打开或处理预览图片:\n{preview_image_path}\n错误: {open_err}")
                 logger.error(f"无法打开或转换预览图片 {preview_image_path}: {open_err}")
                 return

            if is_adaptive:
                final_font_size = self.calculate_adaptive_font_size(final_watermark_text, base_font_size, (img_w, img_h), self.font_chinese, self.font_english)
            else:
                final_font_size = base_font_size
            logger.info(f"预览：最终字体大小: {final_font_size}")

            font_chinese = self.get_font_style(self.font_chinese, final_font_size)
            font_english = self.get_font_style(self.font_english, final_font_size)

            text_width, text_height = self.calculate_text_size(final_watermark_text, img_w, font_chinese, font_english)
            logger.info(f"预览：计算文本尺寸: 宽度={text_width}, 高度={text_height}")

            x_start, y_start = self.calculate_position((img_w, img_h), (text_width, text_height), position)
            logger.info(f"预览：计算水印位置: X={x_start}, Y={y_start}")

            final_color_rgb = self.color
            if is_high_contrast:
                logger.info("预览：启用高对比度模式，计算对比色...")
                box_left = max(0, x_start); box_top = max(0, y_start)
                box_right = min(img_w, x_start + text_width); box_bottom = min(img_h, y_start + text_height)
                watermark_bbox = (box_left, box_top, box_right, box_bottom)

                if watermark_bbox[2] > watermark_bbox[0] and watermark_bbox[3] > watermark_bbox[1]:
                    region_to_analyze = image_rgba.crop(watermark_bbox)
                    contrast_color_rgb = self._calculate_contrast_color(region_to_analyze)
                    final_color_rgb = contrast_color_rgb
                    logger.info(f"预览：高对比度模式计算结果: RGB={final_color_rgb}")
                else:
                    logger.warning("预览：高对比度模式下计算的水印区域无效，使用用户颜色。")
            else:
                logger.info(f"预览：未使用高对比度模式，使用用户颜色 RGB={final_color_rgb}")

            watermark_layer = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(watermark_layer)
            self.draw_watermark(draw, final_watermark_text, x_start, y_start, img_w, font_chinese, font_english, final_color_rgb, opacity_value)

            preview_image = Image.alpha_composite(image_rgba, watermark_layer)
            preview_image.show(title=f"水印预览 - {image_files[0]}")
            logger.info("预览窗口已显示")

        except ValueError as e:
             messagebox.showwarning("参数错误", f"输入无效: {e}")
             logger.warning(f"预览参数验证失败: {e}")
        except Exception as e:
            messagebox.showerror("预览错误", f"预览水印时发生意外错误：\n{str(e)}")
            logger.error(f"预览时发生错误: {e}")
            logger.error(traceback.format_exc())

    # --- 启动处理线程 ---
    def start_processing_thread(self):
        """启动后台线程来执行批量加水印任务，避免阻塞 GUI"""
        if self.processing_thread and self.processing_thread.is_alive():
            messagebox.showwarning("处理中", "当前已有处理任务在运行，请稍候。")
            logger.warning("用户尝试在处理过程中再次启动处理。")
            return

        logger.info("准备开始批量处理...")
        if not self.selected_folder:
            messagebox.showwarning("未选择文件夹", "请先选择一个包含图片的文件夹！")
            logger.warning("处理请求：未选择文件夹。")
            return

        try:
            base_watermark_text, base_font_size, opacity_percent, position = self._get_validated_params()
            opacity_value = int(opacity_percent * 255 / 100)
            is_adaptive = self.multi_size_var.get() == "1"
            is_high_contrast = self.high_contrast_var.get() == "1"
            contains_dynamic = "{exif_date}" in base_watermark_text

            # --- 新增: 重置停止标志 ---
            self.stop_requested = False

            # 禁用控件
            self.process_button.config(state="disabled")
            self.select_button.config(state="disabled")
            self.preview_button.config(state="disabled")
            self.save_button.config(state="disabled")
            self.exit_button.config(state="disabled")
            self.entry_text.config(state="disabled")
            self.entry_font_size.config(state="disabled")
            self.multi_size_check.config(state="disabled")
            self.entry_opacity.config(state="disabled")
            self.color_button.config(state="disabled")
            self.high_contrast_check.config(state="disabled")
            self.position_dropdown.config(state="disabled")
            self.help_icon_label.config(state="disabled")
            # --- 新增: 启用停止按钮 ---
            self.stop_button.config(state="normal")

            # 重置进度
            self.progress["value"] = 0
            self.progress_label.config(text="准备开始...")

            logger.info(f"处理参数: 基础文本='{base_watermark_text}', 基础大小={base_font_size}, "
                       f"透明度={opacity_percent}%, 位置='{position}', 自适应={is_adaptive}, 高对比度={is_high_contrast}")

            # 启动线程
            self.processing_thread = threading.Thread(
                target=self._threaded_add_watermarks,
                args=(base_watermark_text, base_font_size, opacity_value, position, is_adaptive, is_high_contrast, contains_dynamic),
                daemon=True
            )
            self.processing_thread.start()

            # 启动队列检查
            self.master.after(100, self._check_queue)

        except ValueError as e:
            messagebox.showwarning("参数错误", f"输入无效，无法开始处理: {e}")
            logger.warning(f"处理参数验证失败: {e}")
            self._enable_controls() # 发生错误时要重新启用控件
        except Exception as e:
            messagebox.showerror("启动错误", f"启动处理时发生意外错误：\n{str(e)}")
            logger.critical(f"启动后台处理线程时发生严重错误: {e}")
            logger.critical(traceback.format_exc())
            self._enable_controls() # 发生错误时要重新启用控件

    # --- 新增: 请求停止处理的方法 ---
    def request_stop_processing(self):
        """当用户点击“停止处理”按钮时调用"""
        if self.processing_thread and self.processing_thread.is_alive():
            logger.info("用户请求停止处理...")
            self.stop_requested = True
            self.stop_button.config(state="disabled") # 禁用停止按钮本身，防止重复点击
            self.progress_label.config(text="正在停止处理...") # 更新状态提示
        else:
            logger.warning("请求停止，但没有处理线程在运行。")

    # --- 后台线程执行的函数 ---
    def _threaded_add_watermarks(self, base_watermark_text, base_font_size, opacity_value, position, is_adaptive, is_high_contrast, contains_dynamic):
        """在后台线程中执行实际的图片处理循环"""
        processed_count = 0
        skipped_count = 0
        error = None # 用于记录循环中发生的第一个严重错误
        try:
            self.output_folder = os.path.join(self.selected_folder, "Watermarked_Images")
            os.makedirs(self.output_folder, exist_ok=True)
            logger.info(f"输出文件夹: {self.output_folder}")

            supported_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')
            image_files = [f for f in os.listdir(self.selected_folder)
                           if os.path.isfile(os.path.join(self.selected_folder, f)) and f.lower().endswith(supported_extensions)]
            total_images = len(image_files)

            if total_images == 0:
                logger.info("未找到支持的图片，后台线程即将结束。")
                self.processing_queue.put(('finished', 0, 0, None))
                return

            logger.info(f"后台线程：找到 {total_images} 张图片进行处理。")

            for i, filename in enumerate(image_files):
                # --- 新增: 检查停止请求 ---
                if self.stop_requested:
                    logger.info("后台线程：检测到停止请求，中断处理循环。")
                    break # 跳出 for 循环

                current_progress = i + 1
                progress_text = f"处理中: {filename} ({current_progress}/{total_images})"
                self.processing_queue.put(('progress', current_progress, total_images, progress_text))

                try:
                    self.process_single_image(filename, base_watermark_text, base_font_size, opacity_value, position, is_adaptive, is_high_contrast, contains_dynamic)
                    processed_count += 1
                except Exception as img_err:
                    skipped_count += 1
                    error_message = f"处理图片 {filename} 时出错: {img_err}"
                    logger.error(error_message)
                    logger.error(traceback.format_exc())
                    self.processing_queue.put(('error', filename, error_message))
                    # 可以选择在这里也检查停止标志，如果希望出错后也能快速停止
                    # if self.stop_requested: break

            # --- 修改: 记录处理循环结束状态 ---
            if self.stop_requested:
                logger.info("后台线程：处理循环因停止请求而提前结束。")
            else:
                logger.info(f"后台线程：处理循环完成. 成功: {processed_count}, 失败/跳过: {skipped_count}")

        except Exception as e:
            # 捕获创建目录、列出文件等循环外的错误
            error = str(e)
            logger.critical(f"后台处理线程发生严重错误: {e}")
            logger.critical(traceback.format_exc())
            # 即使发生严重错误，也发送 'finished' 信号，以便主线程知道线程已结束
            # 将错误信息传递出去
            self.processing_queue.put(('finished', processed_count, skipped_count, error))
            return

        # 发送最终完成信号 (无论是否被停止或有错误)
        self.processing_queue.put(('finished', processed_count, skipped_count, error))


    # --- 定期检查队列的函数 ---
    def _check_queue(self):
        """在主线程中运行，检查后台线程通过队列发送的消息并更新 GUI"""
        try:
            message = self.processing_queue.get_nowait()

            if message[0] == 'progress':
                # 只有在没有停止请求时才更新进度，避免停止后进度条又跳动
                if not self.stop_requested:
                    current_val, total_val, text = message[1], message[2], message[3]
                    self.progress["value"] = current_val
                    self.progress["maximum"] = total_val
                    self.progress_label.config(text=text)

            elif message[0] == 'error':
                filename, error_msg = message[1], message[2]
                logger.warning(f"处理失败: {filename} - {error_msg[:100]}...")

            elif message[0] == 'finished':
                processed, skipped, error_str = message[1], message[2], message[3]
                self._handle_completion(processed, skipped, error_str)
                return # 完成后停止检查队列

            # 继续安排下一次检查
            self.master.after(100, self._check_queue)

        except queue.Empty:
            # 队列为空，继续安排下一次检查
            self.master.after(100, self._check_queue)
        except Exception as e:
            logger.error(f"检查队列或更新 GUI 时出错: {e}")
            logger.error(traceback.format_exc())
            # 即使出错，也尝试继续检查，除非错误严重到无法恢复
            self.master.after(100, self._check_queue)

    # --- 处理完成后的操作 ---
    def _handle_completion(self, processed_count, skipped_count, error_str):
        """在主线程中处理完成事件，如显示结果、重新启用控件"""
        logger.info("收到后台线程完成信号。")

        # --- 新增: 检查是否是用户停止的 ---
        was_stopped = self.stop_requested
        # --- 新增: 重置停止标志，为下次运行做准备 ---
        self.stop_requested = False

        # 清理进度显示
        self.progress["value"] = 0
        # 根据结束状态设置最终的进度标签文本
        if was_stopped:
             self.progress_label.config(text="处理已停止")
        elif error_str:
             self.progress_label.config(text="处理因错误结束")
        else:
             self.progress_label.config(text="处理完成")

        # 启用控件 (现在 _enable_controls 也会禁用停止按钮)
        self._enable_controls()

        # 重置线程引用
        self.processing_thread = None

        # 显示结果
        if error_str:
            messagebox.showerror("处理失败", f"批量处理过程中发生严重错误，可能未完全处理：\n{error_str}\n\n已处理: {processed_count} 张\n跳过/失败: {skipped_count} 张\n\n请检查控制台或日志区域获取详细信息。")
        # --- 修改: 根据是否停止显示不同消息 ---
        elif was_stopped:
            completion_message = f"处理已由用户停止。\n\n处理图片: {processed_count} 张\n跳过/失败: {skipped_count} 张"
            if processed_count > 0 or skipped_count > 0:
                 completion_message += f"\n\n部分结果可能保存在:\n{self.output_folder}"
            messagebox.showwarning("处理已停止", completion_message) # 使用警告框提示用户停止
        else:
            completion_message = f"处理完成！\n\n成功处理: {processed_count} 张图片\n跳过/失败: {skipped_count} 张图片"
            if skipped_count > 0:
                completion_message += "\n(失败详情请查看日志区域或控制台)"
            completion_message += f"\n\n水印图片保存在:\n{self.output_folder}"
            messagebox.showinfo("处理完成", completion_message)

            # 询问打开文件夹 (只有正常完成且有成功处理时才询问)
            if processed_count > 0 and not was_stopped and not error_str:
                if messagebox.askyesno("打开文件夹", "处理完成，是否立即打开输出文件夹？"):
                    self.open_output_folder()

    # --- 启用 GUI 控件 ---
    def _enable_controls(self):
        """重新启用在处理期间被禁用的控件，并禁用停止按钮"""
        self.process_button.config(state="normal")
        self.select_button.config(state="normal")
        self.preview_button.config(state="normal")
        self.save_button.config(state="normal")
        self.exit_button.config(state="normal")
        # 启用设置相关的输入框和下拉菜单等
        self.entry_text.config(state="normal")
        self.entry_font_size.config(state="normal")
        self.multi_size_check.config(state="normal")
        self.entry_opacity.config(state="normal")
        self.color_button.config(state="normal")
        self.high_contrast_check.config(state="normal")
        self.position_dropdown.config(state="readonly")
        self.help_icon_label.config(state="normal")
        # --- 新增/修改: 确保停止按钮被禁用 ---
        self.stop_button.config(state="disabled")

        logger.debug("GUI 控件已重新启用 (停止按钮已禁用)。")

    # --- 获取并验证用户输入的参数 ---
    def _get_validated_params(self):
        """验证用户在 GUI 中输入的参数是否有效，无效则抛出 ValueError"""
        watermark_text = self.entry_text.get().strip()
        if not watermark_text:
            raise ValueError("水印内容不能为空！")

        try:
            font_size = int(self.entry_font_size.get())
            if font_size <= 0:
                raise ValueError("字体大小必须是正整数！")
        except ValueError:
            raise ValueError("字体大小必须是有效的正整数！")

        try:
            opacity = int(self.entry_opacity.get())
            if not 0 <= opacity <= 100:
                raise ValueError("透明度必须在 0 到 100 之间！")
        except ValueError:
            raise ValueError("透明度必须是 0 到 100 之间的有效整数！")

        position = self.position_var.get()
        if position not in self.position_options:
             logger.warning(f"获取参数时发现无效的位置 '{position}'，强制回退到 '右下角'")
             position = "右下角"

        return watermark_text, font_size, opacity, position

    # --- 计算自适应字体大小 ---
    def calculate_adaptive_font_size(self, text, base_font_size, image_size, font_chinese_path, font_english_path):
        """根据图片宽度、文本内容和基础字体大小，计算一个视觉上更和谐的字体大小"""
        if not text:
            logger.warning("自适应大小计算：文本为空，返回基础大小。")
            return base_font_size

        img_w, img_h = image_size
        target_width = img_w * 0.80
        min_font_size = max(10, int(min(img_w, img_h) * 0.015))
        max_font_size = int(min(img_w, img_h) * 0.30)
        max_font_size = max(min_font_size + 1, max_font_size)

        best_size = min_font_size
        low, high = min_font_size, max_font_size

        logger.debug(f"自适应计算开始: 目标宽度={target_width:.0f}, 字体范围=[{low}-{high}], 基础大小={base_font_size}")

        max_iterations = 10
        for i in range(max_iterations):
            if low > high: break
            mid = (low + high) // 2
            if mid <= 0: break

            try:
                temp_font_chinese = self.get_font_style(font_chinese_path, mid)
                temp_font_english = self.get_font_style(font_english_path, mid)
                current_width, _ = self.calculate_text_size(text, float('inf'), temp_font_chinese, temp_font_english, calculate_only=True)
                logger.debug(f"  测试大小={mid}, 计算单行宽度={current_width:.0f}")

                if current_width <= target_width:
                    best_size = mid
                    low = mid + 1
                else:
                    high = mid - 1
            except Exception as e:
                logger.warning(f"计算自适应字体大小时 (size={mid}) 出错: {e}. 尝试更小尺寸.")
                high = mid - 1

        final_size = max(min_font_size, min(best_size, max_font_size))
        logger.info(f"自适应字体计算结果: {final_size} (基础={base_font_size}, 目标宽度={target_width:.0f}, 范围=[{min_font_size}-{max_font_size}])")
        return final_size

    # --- 计算文本尺寸 (考虑换行) ---
    def calculate_text_size(self, text, max_width_constraint, font_chinese, font_english, calculate_only=False):
        """计算文本在给定字体和最大宽度约束下的渲染尺寸（宽度和高度）。"""
        if not text: return 0, 0

        lines_data = []
        current_line = ""
        current_width = 0
        max_char_height_overall = 0
        max_line_width = 0
        total_height = 0
        current_line_max_h = 0

        try:
            temp_img = Image.new('RGBA', (1, 1))
            temp_draw = ImageDraw.Draw(temp_img)
            use_bbox = hasattr(temp_draw, 'textbbox')
            if use_bbox: logger.debug("文本尺寸计算：使用 textbbox 方法。")
            else: logger.debug("文本尺寸计算：textbbox 不可用, 使用 getsize/getlength 后备方法。")
        except Exception as check_err:
            use_bbox = False
            logger.warning(f"检查 textbbox 可用性时出错: {check_err}, 使用后备方法。")

        for char_index, char in enumerate(text):
            is_cjk = is_chinese(char)
            font = font_chinese if is_cjk else font_english

            char_width, char_height = 10, 10
            try:
                if use_bbox:
                    bbox = temp_draw.textbbox((0, 0), char, font=font)
                    char_width = bbox[2] - bbox[0]
                    char_height = bbox[3] - bbox[1]
                elif hasattr(font, 'getsize'):
                    size = font.getsize(char)
                    char_width, char_height = size[0], size[1]
                elif hasattr(font, 'getlength'):
                    char_width = font.getlength(char)
                    char_height = font.size if hasattr(font, 'size') else char_width
                else:
                     char_width = font.size if hasattr(font, 'size') else 10
                     char_height = font.size if hasattr(font, 'size') else 10
            except Exception as e:
                logger.warning(f"无法获取字符 '{char}' 尺寸: {e}. 使用默认值 ({char_width}x{char_height}). Font: {font}")

            max_char_height_overall = max(max_char_height_overall, char_height)
            current_line_max_h = max(current_line_max_h, char_height)

            if calculate_only:
                current_width += char_width
            else:
                # 检查是否需要换行（当前行非空且加上新字符会超宽）
                # 注意: 这里的 max_width_constraint 是图片的宽度，应该用于 draw_watermark，
                # calculate_text_size 主要用于计算理想尺寸，这里暂时用 inf
                # if current_width > 0 and (current_width + char_width) > max_width_constraint:
                # 改为由 draw_watermark 决定换行，这里只计算总尺寸
                current_width += char_width
                current_line += char


        # if calculate_only:
        #     return current_width, max_char_height_overall
        # else:
        #     if current_line:
        #         lines_data.append((current_line, current_width, current_line_max_h))
        #         max_line_width = max(max_line_width, current_width)
        #         total_height += current_line_max_h
        #     logger.debug(f"计算文本尺寸结果 (单行估算): 最大宽度={max_line_width}, 总高度={total_height}")
        #     # 注意：这里返回的是单行估算的总宽度和最大字符高度，换行由 draw_watermark 处理
        #     return max_line_width, total_height

        # --- 简化: 返回单行总宽度估算和最大字符高度 ---
        # 实际换行和最终尺寸由 draw_watermark 控制和隐式决定
        logger.debug(f"计算文本尺寸结果 (估算单行): 宽度={current_width}, 最大字符高度={max_char_height_overall}")
        return current_width, max_char_height_overall


    # --- 绘制水印文本 (考虑换行) ---
    def draw_watermark(self, draw, text, x_start, y_start, max_width_constraint, font_chinese, font_english, color_rgb, opacity_value):
        """在 Pillow Draw 对象上绘制水印文本，自动处理换行。"""
        if not text: return

        logger.debug(f"准备绘制水印: 起点=({x_start},{y_start}), 最大宽度约束={max_width_constraint}, 颜色RGB={color_rgb}, 透明度={opacity_value}")
        try:
            int_color_rgb = tuple(int(c) for c in color_rgb)
            int_opacity = int(opacity_value)
            fill_color = (*int_color_rgb, int_opacity)
        except (ValueError, TypeError, IndexError) as e:
            logger.error(f"无效的颜色或透明度值: color_rgb={color_rgb}, opacity={opacity_value}. Error: {e}. 使用默认黑色不透明.")
            fill_color = (0, 0, 0, 255)

        x, y = float(x_start), float(y_start) # 使用浮点数以提高精度
        current_line_width = 0.0
        current_line_max_h = 0.0
        space_width = 0.0 # 空格宽度

        # 尝试获取空格宽度
        try:
            font_for_space = font_english if font_english else font_chinese
            if hasattr(font_for_space, 'getlength'):
                 space_width = font_for_space.getlength(' ')
            elif hasattr(font_for_space, 'getsize'):
                 space_width = font_for_space.getsize(' ')[0]
            else: # 后备
                 space_width = font_for_space.size / 2 if hasattr(font_for_space, 'size') else 5.0
        except: pass # 忽略获取空格宽度的错误

        words = text.split(' ') # 按空格分割，尝试在单词间换行
        line_buffer = [] # 存储当前行的单词信息

        temp_draw = draw # 用于测量
        use_bbox = hasattr(temp_draw, 'textbbox')

        def get_char_metrics(char, font):
            """获取单个字符的宽度和高度"""
            try:
                if use_bbox:
                    bbox = temp_draw.textbbox((0, 0), char, font=font)
                    return bbox[2] - bbox[0], bbox[3] - bbox[1]
                elif hasattr(font, 'getsize'):
                    size = font.getsize(char)
                    return size[0], size[1]
                elif hasattr(font, 'getlength'):
                    w = font.getlength(char)
                    h = font.size if hasattr(font, 'size') else w
                    return w, h
                else: # 最后手段
                     s = font.size if hasattr(font, 'size') else 10
                     return s, s
            except Exception as e:
                logger.warning(f"获取字符 '{char}' 指标时出错: {e}. 使用默认值 (10x10).")
                return 10.0, 10.0

        def flush_line_buffer(draw_obj, start_x, current_y, buffer):
            """绘制缓冲区中的一行文字"""
            line_text = "".join([item['text'] for item in buffer])
            total_line_height = max(item['height'] for item in buffer) if buffer else 0
            current_x = float(start_x)
            for item in buffer:
                 try:
                    # 基线对齐可能更复杂，这里简单使用顶部对齐绘制
                    draw_obj.text((int(current_x), int(current_y)), item['text'], font=item['font'], fill=fill_color)
                 except Exception as draw_err:
                    logger.error(f"绘制文本块 '{item['text']}' 到 ({int(current_x)}, {int(current_y)}) 时出错: {draw_err}")
                 current_x += item['width']
            return total_line_height

        word_index = 0
        while word_index < len(words):
            word = words[word_index]
            is_first_word_in_line = not line_buffer
            potential_line_width = current_line_width

            if not is_first_word_in_line:
                 potential_line_width += space_width # 加上单词间空格的宽度

            word_width = 0.0
            word_max_h = 0.0
            word_chars_metrics = [] # 存储单词内每个字符的信息

            # 计算整个单词的宽度和高度
            for char in word:
                is_cjk = is_chinese(char)
                font = font_chinese if is_cjk else font_english
                char_w, char_h = get_char_metrics(char, font)
                word_width += char_w
                word_max_h = max(word_max_h, char_h)
                word_chars_metrics.append({'text': char, 'font': font, 'width': char_w, 'height': char_h})

            # 判断加上这个单词（和可能的空格）后是否会超宽
            if potential_line_width + word_width <= max_width_constraint:
                # 不超宽，将单词（和空格）加入缓冲区
                if not is_first_word_in_line:
                    # 添加空格信息
                    space_font = font_english if font_english else font_chinese # 假设空格用英文字体
                    line_buffer.append({'text': ' ', 'font': space_font, 'width': space_width, 'height': get_char_metrics(' ', space_font)[1]})
                    current_line_width += space_width

                line_buffer.extend(word_chars_metrics)
                current_line_width += word_width
                current_line_max_h = max(current_line_max_h, word_max_h)
                word_index += 1 # 处理下一个单词

            else:
                # 超宽了
                if is_first_word_in_line:
                    # 如果是行首第一个单词就超宽了（说明单词本身比行宽还长），强制换行绘制
                    # 这里需要处理长单词内部换行，为了简化，我们先按字符强制换行
                    logger.warning(f"单词 '{word[:20]}...' 太长，将在字符间强制换行。")
                    char_idx_in_word = 0
                    temp_x = float(x_start)
                    temp_h = 0
                    while char_idx_in_word < len(word_chars_metrics):
                         char_metric = word_chars_metrics[char_idx_in_word]
                         if temp_x > x_start and temp_x + char_metric['width'] > x_start + max_width_constraint:
                             # 需要换行
                             y += temp_h if temp_h > 0 else char_metric['height'] # 换到下一行
                             temp_x = float(x_start) # 回到行首
                             temp_h = 0
                         try:
                            draw.text((int(temp_x), int(y)), char_metric['text'], font=char_metric['font'], fill=fill_color)
                         except Exception as draw_err:
                             logger.error(f"绘制长单词字符 '{char_metric['text']}' 到 ({int(temp_x)}, {int(y)}) 时出错: {draw_err}")
                         temp_x += char_metric['width']
                         temp_h = max(temp_h, char_metric['height'])
                         char_idx_in_word += 1
                    y += temp_h # 长单词处理完后，移动到下一行的起始位置
                    current_line_width = 0 # 重置当前行宽
                    current_line_max_h = 0
                    line_buffer = [] # 清空缓冲区
                    word_index += 1 # 这个长单词处理完了

                else:
                    # 不是行首第一个单词超宽，说明当前行已满，需要先绘制当前缓冲区的内容
                    line_height = flush_line_buffer(draw, x_start, y, line_buffer)
                    y += line_height # 移动到下一行
                    line_buffer = [] # 清空缓冲区
                    current_line_width = 0 # 重置当前行宽
                    current_line_max_h = 0
                    # *不* 增加 word_index，让下一个循环重新尝试添加这个放不下的单词到新行

        # 处理循环结束后缓冲区里可能剩下的最后一行
        if line_buffer:
            flush_line_buffer(draw, x_start, y, line_buffer)

        logger.debug("水印文本绘制调用完成.")


    # --- 处理单张图片 ---
    def process_single_image(self, filename, base_watermark_text, base_font_size, opacity_value, position, is_adaptive, is_high_contrast, contains_dynamic):
        """处理单张图片：打开、(可选)修正方向、计算参数、添加水印、保存"""
        image_path = os.path.join(self.selected_folder, filename)
        logger.info(f"开始处理图片: {filename}")
        try:
            original_image = Image.open(image_path)
            original_format = original_image.format
            original_mode = original_image.mode
            logger.debug(f"  原始格式: {original_format}, 原始模式: {original_mode}")

            try:
                corrected_image = ImageOps.exif_transpose(original_image)
                logger.debug("  已尝试根据 EXIF 修正图片方向。")
            except Exception as exif_err:
                logger.warning(f"  尝试修正 EXIF 方向时出错 (将使用原始方向): {exif_err}")
                corrected_image = original_image

            img_w, img_h = corrected_image.size
            logger.debug(f"  图片尺寸 (处理用): {img_w}x{img_h}")

            final_watermark_text = base_watermark_text
            if contains_dynamic:
                logger.debug("  包含动态文本，进行处理...")
                final_watermark_text = self._process_dynamic_text(base_watermark_text, corrected_image)
                logger.debug(f"  处理后水印文本: '{final_watermark_text}'")

            image_rgba = corrected_image.copy().convert("RGBA")

            if is_adaptive:
                final_font_size = self.calculate_adaptive_font_size(final_watermark_text, base_font_size, (img_w, img_h), self.font_chinese, self.font_english)
            else:
                final_font_size = base_font_size
            logger.debug(f"  最终字体大小: {final_font_size}")

            font_chinese = self.get_font_style(self.font_chinese, final_font_size)
            font_english = self.get_font_style(self.font_english, final_font_size)

            # --- 修改: 使用图片的宽度作为换行约束来计算文本尺寸 ---
            # text_width, text_height = self.calculate_text_size(final_watermark_text, img_w * 0.9, font_chinese, font_english) # 使用图片宽度 90% 作为约束
            # --- 改回: 先计算无约束的尺寸，用于定位，绘制时再处理换行 ---
            text_width_estimate, text_height_estimate = self.calculate_text_size(final_watermark_text, float('inf'), font_chinese, font_english, calculate_only=True)
            logger.debug(f"  估算文本尺寸 (单行): 宽度={text_width_estimate}, 高度={text_height_estimate}")
            # 注意：这个估算尺寸用于 calculate_position 定位，实际渲染尺寸可能因换行而变

            # --- 修改: 使用估算尺寸来定位 ---
            x_start, y_start = self.calculate_position((img_w, img_h), (text_width_estimate, text_height_estimate), position)
            logger.debug(f"  计算水印起始位置: X={x_start}, Y={y_start}")

            final_color_rgb = self.color
            if is_high_contrast:
                logger.debug("  启用高对比度模式，计算背景区域颜色...")
                # --- 修改: 使用估算尺寸和位置来确定分析区域 ---
                box_left = max(0, x_start); box_top = max(0, y_start)
                # 估算区域宽度和高度，考虑可能的换行，可以稍微放大一点区域，或者就用单行估算值
                analyze_w = min(img_w - box_left, text_width_estimate) # 限制在图片内
                analyze_h = min(img_h - box_top, text_height_estimate * 1.5) # 高度稍微放大以应对可能的换行
                box_right = box_left + analyze_w; box_bottom = box_top + analyze_h
                watermark_bbox = (int(box_left), int(box_top), int(box_right), int(box_bottom))

                if watermark_bbox[2] > watermark_bbox[0] and watermark_bbox[3] > watermark_bbox[1]:
                    region_to_analyze = image_rgba.crop(watermark_bbox)
                    contrast_color_rgb = self._calculate_contrast_color(region_to_analyze)
                    final_color_rgb = contrast_color_rgb
                    logger.debug(f"  高对比度模式计算结果: RGB={final_color_rgb}")
                else:
                    logger.warning(f"  高对比度模式下估算的水印区域无效 {watermark_bbox}，使用用户颜色。")
            else:
                 logger.debug(f"  未使用高对比度模式，使用用户颜色 RGB={final_color_rgb}")

            watermark_layer = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(watermark_layer)
            # --- 修改: 传递图片宽度作为换行约束 ---
            # 稍微留点边距，比如 95% 宽度
            draw_max_width = img_w * 0.98 - (x_start if position in ["左上角", "左下角", "中心"] else (img_w - (x_start+text_width_estimate)))
            self.draw_watermark(draw, final_watermark_text, x_start, y_start, img_w, font_chinese, font_english, final_color_rgb, opacity_value)

            watermarked_image_rgba = Image.alpha_composite(image_rgba, watermark_layer)

            output_path = os.path.join(self.output_folder, filename)
            file_base, file_ext = os.path.splitext(filename)
            file_ext = file_ext.lower()
            save_format = None
            save_params = {}
            final_image_to_save = watermarked_image_rgba

            if original_format == 'JPEG':
                final_image_to_save = watermarked_image_rgba.convert("RGB")
                save_format = 'JPEG'
                save_params = {'quality': 95, 'optimize': True}
                logger.debug("  目标格式 JPEG：转换为 RGB，设置质量 95 并优化。")
            elif original_format == 'BMP' or file_ext == '.bmp':
                final_image_to_save = watermarked_image_rgba.convert("RGB")
                save_format = 'BMP'
                logger.debug("  目标格式 BMP：转换为 RGB。")
            elif original_format == 'GIF' or file_ext == '.gif':
                # 对于GIF，保留RGBA并保存为PNG以支持透明度（丢失动画）
                output_path = os.path.join(self.output_folder, file_base + ".png") # 改后缀为 png
                save_format = 'PNG'
                # final_image_to_save = watermarked_image_rgba # 保持 RGBA
                logger.warning(f"GIF 文件 {filename} 将作为静态 PNG 图片保存到 {output_path} 以保留透明度。动画将丢失。")
            elif original_format == 'WEBP' or file_ext == '.webp':
                # WebP 支持透明度，直接保存 RGBA
                save_format = 'WEBP'
                save_params = {'lossless': True, 'quality': 100} # 尝试无损保存
                # final_image_to_save = watermarked_image_rgba # 保持 RGBA
                logger.debug("  目标格式 WebP：尝试无损保存。")
            elif original_format == 'PNG' or file_ext == '.png':
                # PNG 支持透明度
                save_format = 'PNG'
                save_params = {'optimize': True}
                # final_image_to_save = watermarked_image_rgba # 保持 RGBA
                logger.debug("  目标格式 PNG：尝试优化保存。")
            else:
                # 其他格式，如果原始模式支持 Alpha，则尝试保存 RGBA (可能保存为 PNG)，否则转 RGB
                if original_mode in ('RGBA', 'LA', 'P'): # 'P' 模式可能包含透明度
                    save_format = 'PNG' # 默认保存为 PNG 以支持可能的透明度
                    output_path = os.path.join(self.output_folder, file_base + ".png")
                    logger.debug(f"  未知或未特殊处理的格式 ({original_format})，且原模式支持 Alpha，尝试保存为 PNG。")
                else:
                     final_image_to_save = watermarked_image_rgba.convert("RGB")
                     # 让 Pillow 自动推断格式或根据扩展名保存，或者指定一个通用格式如 PNG
                     # save_format = None # 或 'PNG'
                     logger.debug(f"  未知或未特殊处理的格式 ({original_format}) 且原模式无 Alpha，尝试转为 RGB 保存。")


            logger.debug(f"  准备保存图片到: {output_path} (格式: {save_format or '自动推断'})")
            final_image_to_save.save(output_path, format=save_format, **save_params)

            logger.info(f"图片处理并保存成功: {filename} -> {os.path.basename(output_path)}")

        except FileNotFoundError:
            logger.error(f"文件未找到: {image_path}")
            raise # 重新抛出，让上层处理
        except Exception as e:
            logger.error(f"处理图片 {filename} 时发生未知错误: {e}")
            logger.error(traceback.format_exc())
            raise # 重新抛出，让上层处理


    # --- 保存设置 ---
    def save_settings(self):
        """保存当前界面上的设置到 settings.json 文件"""
        logger.info("尝试保存设置...")
        settings_path = "settings.json" # 定义路径变量
        try:
            watermark_text, font_size, opacity, position = self._get_validated_params()

            settings = {
                "watermark_text": watermark_text,
                "font_size": str(font_size),
                "opacity": str(opacity),
                "color": list(self.color),
                "position": position,
                "multi_size": self.multi_size_var.get(),
                "high_contrast": self.high_contrast_var.get()
            }

            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)

            logger.info(f"设置已成功保存到 {settings_path}")
            self.master.after(100, lambda: messagebox.showinfo("设置已保存", f"当前水印设置已保存到\n{os.path.abspath(settings_path)}"))

        except ValueError as e:
            messagebox.showwarning("无法保存", f"无法保存设置，输入无效: {e}")
            logger.warning(f"保存设置失败，参数验证错误: {e}")
        except Exception as e:
            logger.error(f"保存设置文件 '{settings_path}' 失败: {str(e)}")
            logger.error(traceback.format_exc())
            messagebox.showerror("保存失败", f"无法写入设置文件 '{settings_path}'：\n{str(e)}")

    # --- 加载设置 ---
    def load_settings(self):
        """程序启动时尝试从 settings.json 加载设置"""
        settings_path = "settings.json"
        logger.info(f"尝试从 {settings_path} 加载设置...")

        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)

                self.entry_text.delete(0, 'end')
                self.entry_text.insert(0, settings.get("watermark_text", "请输入水印 {exif_date}"))

                self.entry_font_size.delete(0, 'end')
                self.entry_font_size.insert(0, settings.get("font_size", "40"))

                self.entry_opacity.delete(0, 'end')
                self.entry_opacity.insert(0, settings.get("opacity", "80"))

                color_value = settings.get("color", [255, 255, 0])
                if isinstance(color_value, (list, tuple)) and len(color_value) >= 3:
                    try:
                        self.color = tuple(int(float(c)) for c in color_value[:3])
                    except (ValueError, TypeError):
                        logger.warning(f"加载的颜色值 {color_value} 无效，使用默认黄色。")
                        self.color = (255, 255, 0)
                else:
                    logger.warning(f"加载的颜色格式 {color_value} 无效，使用默认黄色。")
                    self.color = (255, 255, 0)

                position = settings.get("position", "右下角")
                if position not in self.position_options:
                    logger.warning(f"加载的位置 '{position}' 不在预设选项中, 使用默认 '右下角'.")
                    position = "右下角"
                self.position_var.set(position)

                multi_size_val = settings.get("multi_size", "0")
                self.multi_size_var.set(multi_size_val if multi_size_val in ["0", "1"] else "0")

                high_contrast_val = settings.get("high_contrast", "0")
                self.high_contrast_var.set(high_contrast_val if high_contrast_val in ["0", "1"] else "0")

                logger.info("设置已成功加载。")

            except json.JSONDecodeError as e:
                logger.error(f"加载设置失败：JSON 文件 '{settings_path}' 格式错误。{e}")
                messagebox.showerror("加载失败", f"无法解析设置文件 '{settings_path}'。\n文件可能已损坏。\n将使用默认设置。")
                self._set_default_gui_values()
            except Exception as e:
                logger.error(f"加载设置时发生未知错误: {str(e)}")
                logger.error(traceback.format_exc())
                messagebox.showwarning("加载失败", f"加载设置时出错:\n{e}\n将使用默认设置。")
                self._set_default_gui_values()
        else:
            logger.info(f"设置文件 '{settings_path}' 未找到，使用默认值。")
            self._set_default_gui_values()

    # --- 设置默认 GUI 值 ---
    def _set_default_gui_values(self):
        """当加载设置失败或文件不存在时，设置界面控件为预设的默认值"""
        logger.debug("设置默认 GUI 值。")
        self.entry_text.delete(0, 'end')
        self.entry_text.insert(0, "请输入水印 {exif_date}")
        self.entry_font_size.delete(0, 'end')
        self.entry_font_size.insert(0, "40")
        self.entry_opacity.delete(0, 'end')
        self.entry_opacity.insert(0, "80")
        self.color = (255, 255, 0)
        self.position_var.set("右下角")
        self.multi_size_var.set("0")
        self.high_contrast_var.set("0")

    # --- 打开输出文件夹 ---
    def open_output_folder(self):
        """尝试在操作系统的文件浏览器中打开包含水印图片的输出文件夹"""
        if self.output_folder and os.path.isdir(self.output_folder):
            abs_path = os.path.abspath(self.output_folder)
            logger.info(f"尝试打开输出文件夹: {abs_path}")
            try:
                if sys.platform == "win32":
                    os.startfile(abs_path)
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.Popen(['open', abs_path])
                else: # Linux and other Unix-like
                    try:
                        import subprocess
                        subprocess.Popen(['xdg-open', abs_path])
                    except (ImportError, FileNotFoundError, OSError, Exception) as linux_err:
                        logger.warning(f"xdg-open 不可用或出错 ({linux_err})，尝试使用 webbrowser 打开文件夹 URI。")
                        # webbrowser.open() 在某些Linux桌面环境下可能无法直接打开本地目录
                        # 尝试使用 file:// URI
                        webbrowser.open(f"file://{abs_path}")
            except Exception as e:
                logger.error(f"无法自动打开输出文件夹: {e}")
                messagebox.showwarning("无法打开文件夹", f"无法自动打开输出文件夹。\n请手动导航到:\n{abs_path}")
        else:
            logger.warning(f"输出文件夹 '{self.output_folder}' 不存在或未设置，无法打开。")
            messagebox.showwarning("无法打开", f"输出文件夹不存在或尚未创建:\n{self.output_folder}")

    # --- 退出应用程序 ---
    def quit_app(self):
        """退出应用程序"""
        # 检查是否有线程在运行，如果需要可以尝试更优雅地停止，但目前daemon线程会在主程序退出时自动结束
        if self.processing_thread and self.processing_thread.is_alive():
             logger.warning("处理仍在进行中，但用户请求退出。后台线程将随主程序终止。")
             # 可以选择在这里设置 self.stop_requested = True，但这不保证线程会立即停止
        logger.info("应用程序退出请求")
        self.master.quit()
        self.master.destroy()


# --- 主程序入口 ---
if __name__ == "__main__":
    try:
        logger.info("应用程序启动")
        root = Tk()
        app = WatermarkApp(root)
        root.mainloop()
        logger.info("应用程序正常关闭")
    except Exception as e:
        logger.critical(f"应用程序发生未捕获的严重错误，即将退出: {str(e)}")
        logger.critical(traceback.format_exc())
        try:
            messagebox.showerror("严重错误", f"应用程序遇到无法恢复的错误并需要关闭:\n{str(e)}\n\n请查看控制台输出获取详细信息。")
        except Exception as tk_err:
             print(f"CRITICAL ERROR: {e}\n{traceback.format_exc()}", file=sys.stderr)
             print(f"Tkinter Error during critical failure handling: {tk_err}", file=sys.stderr)
        sys.exit(1)

# --- END OF FILE watermark_app.py ---