#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用工具模块
提供日志设置、资源获取、文件处理等通用功能
"""

import os
import sys
import logging
import traceback
from typing import Optional, Tuple, List
from pathlib import Path

def setup_logging(name: str = "PicToolSuite") -> logging.Logger:
    """设置日志系统

    Args:
        name: 日志记录器名称

    Returns:
        配置好的日志记录器
    """
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 配置日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 清除现有处理器
    logger.handlers.clear()

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器
    log_file = log_dir / f"{name.lower()}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

def get_resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径（用于PyInstaller打包）

    Args:
        relative_path: 相对路径

    Returns:
        绝对路径
    """
    try:
        # PyInstaller创建临时文件夹，将路径存储在_MEIPASS中
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_supported_image_extensions() -> List[str]:
    """获取支持的图片文件扩展名"""
    return [
        '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp',
        '.tiff', '.tif', '.ico', '.ppm', '.pgm', '.pbm'
    ]

def is_image_file(file_path: str) -> bool:
    """检查文件是否为支持的图片格式

    Args:
        file_path: 文件路径

    Returns:
        是否为图片文件
    """
    if not os.path.isfile(file_path):
        return False

    ext = os.path.splitext(file_path)[1].lower()
    return ext in get_supported_image_extensions()

def get_image_files(folder_path: str) -> List[str]:
    """获取文件夹中的所有图片文件

    Args:
        folder_path: 文件夹路径

    Returns:
        图片文件路径列表
    """
    if not os.path.isdir(folder_path):
        return []

    image_files = []
    supported_extensions = get_supported_image_extensions()

    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if is_image_file(file_path):
            image_files.append(file_path)

    return sorted(image_files)

def format_file_size(size_bytes: int) -> str:
    """格式化文件大小

    Args:
        size_bytes: 文件大小（字节）

    Returns:
        格式化的文件大小字符串
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f} {size_names[i]}"

def validate_folder_path(folder_path: str) -> bool:
    """验证文件夹路径是否有效

    Args:
        folder_path: 文件夹路径

    Returns:
        是否有效
    """
    return os.path.isdir(folder_path) and os.access(folder_path, os.R_OK)

def check_disk_space(path: str, min_free_bytes: int = 100 * 1024 * 1024) -> bool:
    """检查磁盘空间
    
    Args:
        path: 检查路径
        min_free_bytes: 最小可用空间（默认100MB）
        
    Returns:
        空间是否充足
    """
    try:
        if sys.platform == "win32":
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(path), None, None, ctypes.pointer(free_bytes))
            return free_bytes.value > min_free_bytes
        else:
            st = os.statvfs(path)
            return (st.f_bavail * st.f_frsize) > min_free_bytes
    except Exception:
        # 如果无法检查（例如权限问题），默认返回True
        return True

def create_output_folder(base_folder: str, suffix: str = "_processed") -> str:
    """创建输出文件夹
    
    Args:
        base_folder: 基础文件夹路径
        suffix: 输出文件夹后缀
        
    Returns:
        输出文件夹路径
    """
    if not check_disk_space(base_folder):
         raise OSError("磁盘空间不足 (少于100MB)")

    output_folder = os.path.join(base_folder, f"{suffix.strip('_')}")
    os.makedirs(output_folder, exist_ok=True)
    return output_folder

def get_unique_filename(folder_path: str, base_name: str, extension: str) -> str:
    """获取唯一的文件名（避免重名）

    Args:
        folder_path: 文件夹路径
        base_name: 基础文件名
        extension: 文件扩展名

    Returns:
        唯一的文件名
    """
    extension = extension.lstrip('.')
    filename = f"{base_name}.{extension}"
    counter = 1

    while os.path.exists(os.path.join(folder_path, filename)):
        filename = f"{base_name}_{counter}.{extension}"
        counter += 1

    return filename

def safe_filename(filename: str) -> str:
    """生成安全的文件名（移除或替换非法字符）

    Args:
        filename: 原始文件名

    Returns:
        安全的文件名
    """
    # Windows非法字符
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '_')

    # 移除控制字符
    filename = ''.join(char for char in filename if ord(char) >= 32)

    # 限制长度
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        max_name_length = 200 - len(ext)
        filename = name[:max_name_length] + ext

    return filename.strip()

def calculate_aspect_ratio(width: int, height: int) -> Tuple[float, float]:
    """计算宽高比

    Args:
        width: 宽度
        height: 高度

    Returns:
        (width_ratio, height_ratio)
    """
    if width == 0 or height == 0:
        return 1.0, 1.0

    gcd = __import__('math').gcd(width, height)
    return width / gcd, height / gcd

def resize_to_fit_dimensions(original_width: int, original_height: int,
                           max_width: int, max_height: int,
                           keep_ratio: bool = True) -> Tuple[int, int]:
    """计算适配指定尺寸的图片尺寸

    Args:
        original_width: 原始宽度
        original_height: 原始高度
        max_width: 最大宽度
        max_height: 最大高度
        keep_ratio: 是否保持宽高比

    Returns:
        (new_width, new_height)
    """
    if not keep_ratio:
        return max_width, max_height

    # 计算缩放比例
    width_ratio = max_width / original_width
    height_ratio = max_height / original_height
    scale_ratio = min(width_ratio, height_ratio)

    new_width = int(original_width * scale_ratio)
    new_height = int(original_height * scale_ratio)

    return new_width, new_height

def get_exif_datetime(image) -> Optional[str]:
    """从图片EXIF数据中获取拍摄时间

    Args:
        image: PIL Image对象

    Returns:
        格式化的时间字符串，如果没有则返回None
    """
    try:
        exif_data = image.getexif()
        if not exif_data:
            return None

        # DateTimeOriginal 标签
        datetime_original = exif_data.get(36867)
        if datetime_original and isinstance(datetime_original, str):
            # 清理字符串并尝试解析
            datetime_original = datetime_original.split('\x00')[0].strip()
            try:
                from datetime import datetime
                dt_obj = datetime.strptime(datetime_original, "%Y:%m:%d %H:%M:%S")
                return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                return datetime_original

        # DateTime 标签（备用）
        datetime_modified = exif_data.get(306)
        if datetime_modified and isinstance(datetime_modified, str):
            datetime_modified = datetime_modified.split('\x00')[0].strip()
            try:
                from datetime import datetime
                dt_obj = datetime.strptime(datetime_modified, "%Y:%m:%d %H:%M:%S")
                return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                return datetime_modified

        return None

    except Exception:
        return None

def is_chinese_char(char: str) -> bool:
    """判断字符是否为中文字符

    Args:
        char: 单个字符

    Returns:
        是否为中文字符
    """
    return '\u4e00' <= char <= '\u9fff'

def contains_chinese(text: str) -> bool:
    """判断文本是否包含中文字符

    Args:
        text: 文本字符串

    Returns:
        是否包含中文
    """
    return any(is_chinese_char(char) for char in text)

def truncate_filename(filename: str, max_length: int = 50) -> str:
    """截断文件名以适应显示

    Args:
        filename: 文件名
        max_length: 最大长度

    Returns:
        截断后的文件名
    """
    if len(filename) <= max_length:
        return filename

    name, ext = os.path.splitext(filename)
    available_length = max_length - len(ext) - 3  # 3 for "..."

    if available_length <= 0:
        return filename[:max_length]

    return f"{name[:available_length]}...{ext}"

def format_duration(seconds: float) -> str:
    """格式化时间长度

    Args:
        seconds: 秒数

    Returns:
        格式化的时间字符串
    """
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.0f}s"
    else:
        hours = int(seconds // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        return f"{hours}h {remaining_minutes}m"

def get_system_info() -> dict:
    """获取系统信息

    Returns:
        系统信息字典
    """
    import platform
    import psutil

    info = {
        'platform': platform.platform(),
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version(),
        'cpu_count': psutil.cpu_count(),
        'memory_total': format_file_size(psutil.virtual_memory().total),
        'memory_available': format_file_size(psutil.virtual_memory().available)
    }

    return info

def handle_exception(func):
    """异常处理装饰器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger = logging.getLogger("ExceptionHandler")
            logger.error(f"函数 {func.__name__} 执行出错: {e}")
            logger.error(traceback.format_exc())
            raise
    return wrapper