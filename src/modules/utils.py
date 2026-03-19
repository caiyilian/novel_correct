import os
import time
import logging
import difflib
from datetime import datetime
from typing import Tuple, Optional

# ==========================================
# 日志系统初始化
# ==========================================
def _setup_logger():
    logger = logging.getLogger("novel_correct")
    logger.setLevel(logging.DEBUG)
    
    # 防止重复添加 handler
    if not logger.handlers:
        # 获取项目根目录 (utils.py 的上上级目录)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # 按年月日创建文件夹
        today_str = datetime.now().strftime("%Y-%m-%d")
        log_dir = os.path.join(base_dir, "logs", today_str)
        os.makedirs(log_dir, exist_ok=True)
        
        # 按时分秒创建日志文件
        time_str = datetime.now().strftime("%H-%M-%S")
        log_file = os.path.join(log_dir, f"run_{time_str}.log")
        
        # 文件处理器 (写入所有 debug 级别以上的日志)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        
        # 定义日志格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        
        # 为了兼容最初的打印，我们在需要的地方再向控制台输出
        # 这里不添加 StreamHandler，避免所有的 debug_print 都输出到控制台，
        # 我们将在 debug_print 函数里控制是否输出到控制台。
    return logger

logger = _setup_logger()

def debug_print(*args, debug=False, **kwargs):
    """
    调试打印函数。
    所有内容都会写入 log 文件。
    如果 debug=True，则同时输出到控制台。
    """
    message = " ".join(str(arg) for arg in args)
    
    # 写入日志文件
    logger.debug(message)
    
    # 根据参数决定是否输出到控制台
    if debug:
        print(*args, **kwargs)

def format_time_duration(seconds: float) -> str:
    """
    将秒数格式化为 HH:MM:SS 格式的字符串
    """
    return time.strftime("%H:%M:%S", time.gmtime(seconds))

def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两段文本的相似度，返回 0.0 到 1.0 之间的浮点数
    """
    matcher = difflib.SequenceMatcher(None, text1, text2)
    return matcher.ratio()

def has_meaningful_changes(original: str, modified: str) -> bool:
    """
    检查是否有实质性修改（忽略纯粹的空白或直接回答"没错"）
    """
    diff = list(difflib.ndiff(original.splitlines(keepends=True), modified.splitlines(keepends=True)))
    changes = [line for line in diff if line.startswith('- ') or line.startswith('+ ')]
    
    if (not changes) or ("".join(modified.split()) == "没错"):
        return False
    return True

def find_consecutive_symbols(content: str, left_symbol: str = "「", right_symbol: str = "」") -> Tuple[Optional[str], Optional[int], Optional[int]]:
    """
    寻找文本中连续出现的相同开闭符号
    返回: (冲突的符号, 当前符号的索引, 上一个同类符号的索引)
    如果没有冲突，返回 (None, None, None)
    """
    last = right_symbol # 默认期待下一个是开符号
    last_index = None
    for index, c in enumerate(content):
        if c in (left_symbol, right_symbol):
            if c == last:
                return (c, index, last_index)
            last = c
            last_index = index
    return (None, None, None)

def find_specific_symbols(content: str, target_symbols: Tuple[str, ...] = ("[", "]")) -> Tuple[Optional[str], Optional[int]]:
    """
    寻找文本中指定的独立异常符号 (例如英文中括号 [ 或 ])
    一旦发现，立即返回该符号及其索引。
    返回: (找到的异常符号, 符号在文本中的索引)
    如果没有找到，返回 (None, None)
    """
    for index, c in enumerate(content):
        if c in target_symbols:
            return (c, index)
    return (None, None)

def get_centered_story_clip(content: str, center_index: int, total_length: int = 800) -> Tuple[str, str, int, int, int]:
    """
    以指定索引为中心，截取一段文本，并提取出核心待修正区域
    返回: (完整上下文切块, 核心修正区域, 起始索引, 结束索引, 单侧上下文保护区长度)
    """
    context_padding_size = total_length // 5
    start = max(center_index - total_length // 2, 0)
    end = min(center_index + total_length // 2, len(content))
    
    # 核心区域的起止点
    start_fix = max(center_index - (total_length // 2 - context_padding_size), 0)
    end_fix = min(center_index + (total_length // 2 - context_padding_size), len(content))
    
    total_story_chunk = content[start:end]
    need_correct_chunk = content[start_fix:end_fix]
    
    return total_story_chunk, need_correct_chunk, start, end, context_padding_size

def extract_all_dialogues(content: str, left_symbol: str = "「", right_symbol: str = "」") -> list:
    """
    提取文本中所有被指定符号包裹的对话内容，并记录其位置和长度
    返回一个字典列表，每个字典包含：
    - content: 对话内容 (包含包裹符号)
    - length: 对话长度
    - start_index: 对话起始索引
    - end_index: 对话结束索引
    - center_index: 对话中心点索引
    """
    dialogues = []
    start_idx = -1
    
    for i, char in enumerate(content):
        if char == left_symbol:
            start_idx = i
        elif char == right_symbol and start_idx != -1:
            end_idx = i + 1 # 包含闭合符号本身
            dialogue_text = content[start_idx:end_idx]
            
            dialogues.append({
                "content": dialogue_text,
                "length": end_idx - start_idx,
                "start_index": start_idx,
                "end_index": end_idx,
                "center_index": start_idx + (end_idx - start_idx) // 2
            })
            # 重置 start_idx 准备寻找下一个
            start_idx = -1
            
    return dialogues

def get_top_k_longest_dialogues(dialogues: list, k: int = 10) -> list:
    """
    从对话列表中提取长度最长的前 K 个对话
    """
    sorted_dialogues = sorted(dialogues, key=lambda x: x['length'], reverse=True)
    return sorted_dialogues[:k]


