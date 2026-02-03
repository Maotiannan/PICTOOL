#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
统一管理所有工具的配置信息
"""

import os
import json
import logging
from typing import Dict, Any, Optional

class ConfigManager:
    """配置管理器"""

    def __init__(self, config_file: str = "pic_tool_config.json"):
        self.config_file = config_file
        self.config = {}
        self.logger = logging.getLogger("ConfigManager")

        # 默认配置
        self.default_config = {
            "app": {
                "theme": "default",
                "language": "zh_CN",
                "auto_save": True,
                "remember_last_folder": True,
                "output_folder_suffix": "_processed"
            },
            "watermark": {
                "text": "MU Group Leo: +86 13819858718",
                "font_size": 40,
                "opacity": 80,
                "color": [255, 255, 0],
                "position": "中心",
                "multi_size": True,
                "high_contrast": True,
                "font_chinese": "Microsoft YaHei",
                "font_english": "Arial"
            },
            "gif": {
                "delay": 500,
                "repeat": 0,
                "quality": 20,
                "width": 400,
                "height": 400,
                "keep_ratio": True
            },
            "pdf": {
                "quality": 95,
                "page_size": "A4",
                "orientation": "portrait",
                "margin": 10
            },
            "paths": {
                "last_folder": "",
                "default_output_folder": ""
            }
        }

    def load_settings(self) -> bool:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)

                # 合并配置（保留新增的默认配置项）
                self.config = self.merge_configs(self.default_config, loaded_config)
                self.logger.info(f"配置文件加载成功: {self.config_file}")
                return True
            else:
                # 使用默认配置
                self.config = self.default_config.copy()
                self.logger.info("配置文件不存在，使用默认配置")
                return False

        except json.JSONDecodeError as e:
            self.logger.error(f"配置文件格式错误: {e}")
            self.config = self.default_config.copy()
            return False
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            self.config = self.default_config.copy()
            return False

    def save_settings(self) -> bool:
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            self.logger.info(f"配置文件保存成功: {self.config_file}")
            return True
        except Exception as e:
            self.logger.error(f"保存配置文件失败: {e}")
            return False

    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置值

        Args:
            key_path: 配置键路径，如 'watermark.font_size'
            default: 默认值

        Returns:
            配置值
        """
        try:
            keys = key_path.split('.')
            value = self.config

            for key in keys:
                value = value[key]

            return value
        except (KeyError, TypeError):
            self.logger.warning(f"配置项不存在: {key_path}，使用默认值: {default}")
            return default

    def set(self, key_path: str, value: Any) -> bool:
        """设置配置值

        Args:
            key_path: 配置键路径，如 'watermark.font_size'
            value: 配置值

        Returns:
            是否设置成功
        """
        try:
            keys = key_path.split('.')
            config = self.config

            # 导航到目标位置
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]

            # 设置值
            config[keys[-1]] = value
            self.logger.debug(f"配置项已更新: {key_path} = {value}")
            return True

        except Exception as e:
            self.logger.error(f"设置配置项失败: {key_path} = {value}, 错误: {e}")
            return False

    def get_section(self, section: str) -> Dict[str, Any]:
        """获取配置节

        Args:
            section: 配置节名称，如 'watermark'

        Returns:
            配置节字典
        """
        return self.config.get(section, {}).copy()

    def update_section(self, section: str, values: Dict[str, Any]) -> bool:
        """更新配置节

        Args:
            section: 配置节名称
            values: 要更新的配置值

        Returns:
            是否更新成功
        """
        try:
            if section not in self.config:
                self.config[section] = {}

            self.config[section].update(values)
            self.logger.info(f"配置节已更新: {section}")
            return True

        except Exception as e:
            self.logger.error(f"更新配置节失败: {section}, 错误: {e}")
            return False

    def reset_to_defaults(self, section: Optional[str] = None) -> bool:
        """重置配置到默认值

        Args:
            section: 要重置的配置节，如果为None则重置所有

        Returns:
            是否重置成功
        """
        try:
            if section:
                if section in self.default_config:
                    self.config[section] = self.default_config[section].copy()
                    self.logger.info(f"配置节已重置到默认值: {section}")
                else:
                    self.logger.warning(f"未知的配置节: {section}")
                    return False
            else:
                self.config = self.default_config.copy()
                self.logger.info("所有配置已重置到默认值")

            return True

        except Exception as e:
            self.logger.error(f"重置配置失败: {e}")
            return False

    def merge_configs(self, default: Dict, loaded: Dict) -> Dict:
        """合并配置（递归合并，保留默认配置中的新项）"""
        result = default.copy()

        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def export_settings(self, file_path: str) -> bool:
        """导出配置到文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            self.logger.info(f"配置已导出到: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"导出配置失败: {e}")
            return False

    def import_settings(self, file_path: str) -> bool:
        """从文件导入配置"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)

            # 合并导入的配置
            self.config = self.merge_configs(self.config, imported_config)
            self.logger.info(f"配置已从文件导入: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"导入配置失败: {e}")
            return False

    def validate_config(self) -> bool:
        """验证配置的有效性"""
        try:
            # 验证必要的配置项
            required_sections = ['app', 'watermark', 'gif', 'pdf', 'paths']
            for section in required_sections:
                if section not in self.config:
                    self.logger.error(f"缺少必要的配置节: {section}")
                    return False

            # 验证水印配置
            watermark_config = self.config['watermark']
            if not isinstance(watermark_config.get('font_size'), (int, float)) or watermark_config.get('font_size') <= 0:
                self.logger.error("水印字体大小配置无效")
                return False

            if not isinstance(watermark_config.get('opacity'), (int, float)) or not (0 <= watermark_config.get('opacity') <= 100):
                self.logger.error("水印透明度配置无效")
                return False

            # 验证GIF配置
            gif_config = self.config['gif']
            if not isinstance(gif_config.get('delay'), (int, float)) or gif_config.get('delay') <= 0:
                self.logger.error("GIF帧延迟配置无效")
                return False

            # 验证PDF配置
            pdf_config = self.config['pdf']
            if pdf_config.get('page_size') not in ['A4', 'A3', 'Letter', 'Legal']:
                self.logger.error("PDF页面大小配置无效")
                return False

            self.logger.info("配置验证通过")
            return True

        except Exception as e:
            self.logger.error(f"配置验证失败: {e}")
            return False