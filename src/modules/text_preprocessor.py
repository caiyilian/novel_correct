"""
文本预处理模块

功能：
1. 连续换行标准化：将多个连续的换行符替换为单个换行符
2. 移除非换行符的空白字符（空格、制表符等）
3. 保留原文的格式结构
"""

import re
import logging
from typing import Optional, Tuple


class TextPreprocessor:
    """文本预处理类"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化文本预处理器
        
        Args:
            logger: 日志记录器实例，若为None则使用默认日志
        """
        self.logger = logger or self._get_default_logger()
        
        # 预编译正则表达式以提高效率
        # 移除非换行符的空白字符（空格、制表符、回车等，但保留换行符\n）
        self.whitespace_pattern = re.compile(r'[^\S\n]')
        # 替换多个连续的换行符为单个换行符
        self.newline_pattern = re.compile(r'\n+')
    
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
    
    def preprocess_text(self, text: str) -> Tuple[str, dict]:
        """
        对文本进行预处理
        
        处理流程：
        1. 移除所有非换行符的空白字符（空格、制表符等）
        2. 将连续多个换行符替换为单个换行符
        
        Args:
            text: 原始文本内容
            
        Returns:
            Tuple[处理后的文本, 统计信息字典]
            统计信息包含：
            - original_length: 原始文本长度
            - processed_length: 处理后文本长度
            - removed_chars: 移除的字干数（包括空白字符和多余换行符）
            - original_newlines: 原始换行符数量
            - processed_newlines: 处理后换行符数量
        """
        try:
            # 记录统计信息
            original_length = len(text)
            original_newlines = text.count('\n')
            
            # 第一步：移除非换行符的空白字符
            step1 = self.whitespace_pattern.sub('', text)
            
            # 第二步：将连续多个换行符替换为单个换行符
            processed_text = self.newline_pattern.sub('\n', step1)
            
            # 计算统计数据
            processed_length = len(processed_text)
            processed_newlines = processed_text.count('\n')
            removed_chars = original_length - processed_length
            
            stats = {
                'original_length': original_length,
                'processed_length': processed_length,
                'removed_chars': removed_chars,
                'original_newlines': original_newlines,
                'processed_newlines': processed_newlines,
                'newline_reduction': original_newlines - processed_newlines
            }
            
            return processed_text, stats
            
        except Exception as e:
            self.logger.error(f"文本预处理出错: {type(e).__name__}: {str(e)}")
            raise
    
    def log_preprocess_stats(self, filename: str, stats: dict) -> None:
        """
        记录预处理统计信息
        
        Args:
            filename: 文件名
            stats: 统计信息字典
        """
        self.logger.info(
            f"✓ 预处理完成: {filename}\n"
            f"    原始长度: {stats['original_length']} 字符\n"
            f"    处理后长度: {stats['processed_length']} 字符\n"
            f"    移除字符数: {stats['removed_chars']}\n"
            f"    原始换行符: {stats['original_newlines']}\n"
            f"    处理后换行符: {stats['processed_newlines']}\n"
            f"    换行符减少: {stats['newline_reduction']}"
        )
