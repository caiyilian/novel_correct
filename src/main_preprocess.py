"""
小说纠错系统 - 预处理主程序

功能：
1. 读取ori_story文件夹下的所有小说文件
2. 对每个文件进行预处理
3. 将处理后的文件输出到processed_story文件夹
4. 生成完整的处理日志和统计报告
"""

import os
import sys
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# 导入模块
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.modules.file_handler import FileHandler
from src.modules.text_preprocessor import TextPreprocessor


class PreprocessPipeline:
    """预处理流程管理类"""
    
    def __init__(self, ori_story_dir: str, output_dir: str, log_dir: str = "logs"):
        """
        初始化预处理管道
        
        Args:
            ori_story_dir: 原始文件目录
            output_dir: 输出文件目录
            log_dir: 日志输出目录
        """
        self.ori_story_dir = ori_story_dir
        self.output_dir = output_dir
        self.log_dir = log_dir
        
        # 创建日志输出目录
        os.makedirs(log_dir, exist_ok=True)
        
        # 初始化logger为None，在_setup_logger中更新
        self.logger = None
        # 设置日志
        self.logger = self._setup_logger()
        
        # 初始化处理器
        self.file_handler = FileHandler(self.logger)
        self.text_preprocessor = TextPreprocessor(self.logger)
        
        # 统计信息
        self.stats = {
            'total_files': 0,
            'success_files': 0,
            'failed_files': 0,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'files_detail': {}
        }
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('PreprocessPipeline')
        logger.setLevel(logging.INFO)
        
        # 清除已有的处理器
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 创建日志文件处理器
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(self.log_dir, f"preprocess_{timestamp}.log")
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        logger.info(f"日志文件: {log_file}")
        
        return logger
    
    def preprocess_single_file(self, file_path: str) -> Dict:
        """
        处理单个文件
        
        Args:
            file_path: 输入文件路径
            
        Returns:
            处理结果字典
        """
        filename = os.path.basename(file_path)
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"处理文件: {filename}")
        self.logger.info(f"{'='*60}")
        
        result = {
            'filename': filename,
            'success': False,
            'input_path': file_path,
            'output_path': None,
            'read_error': None,
            'preprocess_stats': None,
            'write_error': None
        }
        
        # 第一步：读取文件
        success, content, error = self.file_handler.read_file(file_path)
        if not success:
            result['read_error'] = str(error)
            self.logger.error(f"✗ 读取失败: {error}")
            return result
        
        # 第二步：预处理文本
        try:
            processed_content, stats = self.text_preprocessor.preprocess_text(content)
            result['preprocess_stats'] = stats
            self.text_preprocessor.log_preprocess_stats(filename, stats)
        except Exception as e:
            error_msg = f"预处理出错: {str(e)}"
            result['preprocess_error'] = error_msg
            self.logger.error(f"✗ {error_msg}")
            return result
        
        # 第三步：写入输出文件
        output_path = os.path.join(self.output_dir, filename)
        success, error = self.file_handler.write_file(output_path, processed_content)
        
        result['output_path'] = output_path
        
        if not success:
            result['write_error'] = str(error)
            self.logger.error(f"✗ 写入失败: {error}")
            return result
        
        result['success'] = True
        self.logger.info(f"✓ 处理完成: {filename}\n")
        return result
    
    def run(self) -> bool:
        """
        执行预处理流程
        
        Returns:
            是否全部处理成功
        """
        self.logger.info(f"\n{'#'*60}")
        self.logger.info("小说预处理流程启动")
        self.logger.info(f"{'#'*60}")
        self.logger.info(f"源文件目录: {os.path.abspath(self.ori_story_dir)}")
        self.logger.info(f"输出目录: {os.path.abspath(self.output_dir)}")
        
        # 获取所有txt文件
        success, file_list, error = self.file_handler.read_directory(
            self.ori_story_dir, 
            pattern="*.txt"
        )
        
        if not success:
            self.logger.error(f"✗ 无法读取源文件目录: {error}")
            return False
        
        if not file_list:
            self.logger.error("✗ 源文件目录中未找到任何.txt文件")
            return False
        
        self.logger.info(f"找到 {len(file_list)} 个文件待处理\n")
        self.stats['total_files'] = len(file_list)
        
        # 处理每个文件
        for file_path in file_list:
            result = self.preprocess_single_file(file_path)
            
            self.stats['files_detail'][os.path.basename(file_path)] = result
            
            if result['success']:
                self.stats['success_files'] += 1
            else:
                self.stats['failed_files'] += 1
        
        # 记录统计信息
        self.stats['end_time'] = datetime.now().isoformat()
        self._log_summary()
        self._save_stats()
        
        return self.stats['failed_files'] == 0
    
    def _log_summary(self) -> None:
        """记录处理总结"""
        self.logger.info(f"\n{'#'*60}")
        self.logger.info("预处理流程完成")
        self.logger.info(f"{'#'*60}")
        self.logger.info(f"总文件数: {self.stats['total_files']}")
        self.logger.info(f"成功: {self.stats['success_files']}")
        self.logger.info(f"失败: {self.stats['failed_files']}")
        
        if self.stats['success_files'] > 0:
            success_files = [f for f, r in self.stats['files_detail'].items() if r['success']]
            self.logger.info(f"\n✓ 成功处理的文件:")
            for f in sorted(success_files):
                stats = self.stats['files_detail'][f]['preprocess_stats']
                if stats:
                    self.logger.info(
                        f"  - {f} "
                        f"(原: {stats['original_length']} -> 处理后: {stats['processed_length']})"
                    )
        
        if self.stats['failed_files'] > 0:
            failed_files = [f for f, r in self.stats['files_detail'].items() if not r['success']]
            self.logger.info(f"\n✗ 处理失败的文件:")
            for f in failed_files:
                result = self.stats['files_detail'][f]
                error = result.get('read_error') or result.get('preprocess_error') or result.get('write_error')
                self.logger.error(f"  - {f}: {error}")
        
        self.logger.info(f"{'#'*60}\n")
    
    def _save_stats(self) -> None:
        """保存统计信息到JSON文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stats_file = os.path.join(self.log_dir, f"preprocess_stats_{timestamp}.json")
        
        try:
            # 简化统计信息用于JSON序列化
            simplified_stats = {
                'total_files': self.stats['total_files'],
                'success_files': self.stats['success_files'],
                'failed_files': self.stats['failed_files'],
                'start_time': self.stats['start_time'],
                'end_time': self.stats['end_time'],
                'files_detail': {}
            }
            
            for filename, result in self.stats['files_detail'].items():
                simplified_stats['files_detail'][filename] = {
                    'success': result['success'],
                    'preprocess_stats': result['preprocess_stats'],
                    'errors': {
                        'read_error': result.get('read_error'),
                        'preprocess_error': result.get('preprocess_error'),
                        'write_error': result.get('write_error')
                    }
                }
            
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(simplified_stats, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"统计信息已保存: {stats_file}")
        except Exception as e:
            self.logger.error(f"保存统计信息出错: {str(e)}")


def main():
    """主函数"""
    # 当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 定义路径
    ori_story_dir = os.path.join(script_dir, "ori_story")
    output_dir = os.path.join(script_dir, "processed_story")
    log_dir = os.path.join(script_dir, "logs")
    
    # 创建且执行预处理流程
    pipeline = PreprocessPipeline(ori_story_dir, output_dir, log_dir)
    
    success = pipeline.run()
    
    # 返回exit code
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
