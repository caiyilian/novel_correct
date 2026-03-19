"""
文件读写模块

功能：
1. 按照UTF-16编码、Unix (LF)换行符格式读取文本文件
2. 按照UTF-16编码、Unix (LF)换行符格式写入文本文件
3. 支持异常捕获与错误日志
"""

import os
import logging
from typing import Optional, Tuple
from pathlib import Path


class FileHandler:
    """文件读写处理类"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化文件处理器
        
        Args:
            logger: 日志记录器实例，若为None则使用默认日志
        """
        self.logger = logger or self._get_default_logger()
    
    @staticmethod
    def _get_default_logger() -> logging.Logger:
        """获取默认日志记录器"""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def read_file(self, file_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        读取文本文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            Tuple[成功标志, 文件内容, 错误信息]
            - 成功时: (True, 文本内容, None)
            - 失败时: (False, None, 错误信息)
        """
        try:
            # 验证文件是否存在
            if not os.path.exists(file_path):
                error_msg = f"文件不存在: {file_path}"
                self.logger.error(error_msg)
                return False, None, error_msg
            
            # 验证是否为文件
            if not os.path.isfile(file_path):
                error_msg = f"路径不是文件: {file_path}"
                self.logger.error(error_msg)
                return False, None, error_msg
            
            # 以UTF-16编码读取文件
            with open(file_path, 'r', encoding='utf-16', newline='') as f:
                content = f.read()
            
            self.logger.info(f"✓ 成功读取文件: {file_path} (字符数: {len(content)})")
            return True, content, None
            
        except UnicodeDecodeError as e:
            error_msg = f"字符编码错误 - {file_path}: {str(e)}"
            self.logger.error(error_msg)
            return False, None, error_msg
        except PermissionError as e:
            error_msg = f"权限不足，无法读取文件 - {file_path}: {str(e)}"
            self.logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"读取文件时出错 - {file_path}: {type(e).__name__}: {str(e)}"
            self.logger.error(error_msg)
            return False, None, error_msg
    
    def write_file(self, file_path: str, content: str) -> Tuple[bool, Optional[str]]:
        """
        写入文本文件
        
        Args:
            file_path: 文件输出路径
            content: 文件内容
            
        Returns:
            Tuple[成功标志, 错误信息]
            - 成功时: (True, None)
            - 失败时: (False, 错误信息)
        """
        try:
            # 创建目录（如果不存在）
            output_dir = os.path.dirname(file_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                self.logger.info(f"✓ 创建输出目录: {output_dir}")
            
            # 以UTF-16编码写入文件，使用Unix换行符
            # newline='' 确保换行符不被自动转换
            with open(file_path, 'w', encoding='utf-16', newline='') as f:
                f.write(content)
            
            self.logger.info(f"✓ 成功写入文件: {file_path} (字符数: {len(content)})")
            return True, None
            
        except PermissionError as e:
            error_msg = f"权限不足，无法写入文件 - {file_path}: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
        except IOError as e:
            error_msg = f"IO错误 - {file_path}: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"写入文件时出错 - {file_path}: {type(e).__name__}: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def read_directory(self, dir_path: str, pattern: str = "*.txt") -> Tuple[bool, list, Optional[str]]:
        """
        读取目录下的所有匹配文件
        
        Args:
            dir_path: 目录路径
            pattern: 文件匹配模式（如 "*.txt"）
            
        Returns:
            Tuple[成功标志, 文件路径列表, 错误信息]
        """
        try:
            if not os.path.exists(dir_path):
                error_msg = f"目录不存在: {dir_path}"
                self.logger.error(error_msg)
                return False, [], error_msg
            
            if not os.path.isdir(dir_path):
                error_msg = f"路径不是目录: {dir_path}"
                self.logger.error(error_msg)
                return False, [], error_msg
            
            # 使用Path获取匹配的文件
            dir_obj = Path(dir_path)
            file_paths = sorted([str(f) for f in dir_obj.glob(pattern)])
            
            self.logger.info(f"✓ 找到 {len(file_paths)} 个文件: {pattern}")
            return True, file_paths, None
            
        except Exception as e:
            error_msg = f"读取目录时出错 - {dir_path}: {type(e).__name__}: {str(e)}"
            self.logger.error(error_msg)
            return False, [], error_msg
