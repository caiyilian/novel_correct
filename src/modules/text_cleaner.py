import re

def normalize_whitespaces(text: str) -> str:
    """
    预处理文本：
    1. 去除所有非换行符的空白字符
    2. 将连续的多个换行符压缩为单个换行符
    """
    return re.sub(r'\n+', '\n', re.sub(r'[^\S\n]', '', text))

def extract_and_clean_llm_output(original_text: str, llm_output: str) -> str:
    """
    智能清理大模型输出
    1. 去除 markdown 代码块包裹符号
    2. 根据原始输入(original_text)的首尾空白字符习惯，调整输出(llm_output)
    """
    # 0. 预处理：去掉两端可能存在的空白字符（防止正则匹配失败）
    llm_output = llm_output.strip()

    # 1. 去除 markdown 代码块 (包括 ``` 和 ```python 等)
    # 尝试匹配被 ``` 包裹的内容
    # re.DOTALL 使得 . 可以匹配换行符
    match = re.search(r'^```(?:\w+)?\s*\n(.*?)\n\s*```$', llm_output, re.DOTALL)
    if match:
        cleaned = match.group(1)
    else:
        # 如果没有匹配到完整的代码块，尝试简单的去除
        cleaned = llm_output.replace("```", "")

    # 2. 智能调整首尾空白
    # 获取原始输入的首尾空白字符 (在这里主要是换行符，因为用户代码里已经去除了空格)
    original_leading_ws = original_text[:len(original_text) - len(original_text.lstrip())]
    original_trailing_ws = original_text[len(original_text.rstrip()):]

    # 去除输出内容的首尾空白
    content = cleaned.strip()

    # 重新组合：原始前导空白 + 清理后的内容 + 原始后置空白
    final_result = original_leading_ws + content + original_trailing_ws
    
    return final_result
