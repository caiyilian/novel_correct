import os
import time
from typing import Tuple, List, Dict
from tqdm import tqdm

# 从本地模块导入工具函数
from src.modules.text_cleaner import normalize_whitespaces
from src.modules.utils import debug_print, format_time_duration
from src.modules.corrector_core import request_multi_model_correction, log_error_results, apply_chunk_correction

def build_correction_prompt(current_chunk: str, target_correction_area: str) -> str:
    """
    构建发给大模型的Prompt
    """
    correction_prompt = f"""### 强制执行规则（100%遵守，禁止任何偏离）
        1.  小说人物对话的唯一合法包裹符号，是成对的全角直角引号「」，其他任何括号、引号均不合法。
        2.  我会发给你两个片段，一个是**原始小说片段**，一个是从**原始小说片段**中间截取的**修正待检查内容**
        2.  仅检查并修正**待检查内容**中「」的使用错误（比如用[、【、"等替代「的错误），或者缺少的情况就要补上，多余的情况就要删去。
        3.  **原始小说片段**包含了修正待检查内容，还包含了两侧的**非修正待检查内容**，**非修正待检查内容**只是作为上下文给你一个完整语境参考，以及防止截取片段把对话截断的时候让你产生误解
        4.  **绝对禁止**续写或者补全句子。如果**修正待检查内容**在句子中间断开，你的输出也必须在完全相同的地方断开。
        5.  **绝对禁止**输出任何解释性文字、前缀或后缀。只输出修正后的文本本身。
        6.  最终返回修正后的**修正待检查内容**,不要输出其他额外内容。
        7.  如果**修正待检查内容**没有需要修正的地方，直接输出"没错"2字。

        ---

        **原始小说片段** (仅供参考语境，不要输出):
        ```
        {current_chunk}
        ```

        ---

        **修正待检查内容** (请直接修正此内容，保持原有截断):
        ```
        {target_correction_area}
        ```
    """
    return normalize_whitespaces(correction_prompt)

def process_single_chunk(full_volume_text: str, start: int, end: int, context_padding_size: int, similarity_threshold: float, debug: bool, error_log_path: str, stats: Dict[str, int], min_models_to_agree: int = 1) -> Tuple[str, int]:
    """
    处理单个文本块的修正逻辑，返回 (更新后的全文, 长度变化增量)
    """
    current_chunk = full_volume_text[start:end]
    if len(current_chunk) != (end - start):
        return full_volume_text, 0
        
    current_chunk = normalize_whitespaces(current_chunk)
    
    # ✨ 动态计算实际的前后context大小
    # 处理开头：如果start接近文本开头，减少前context
    context_front = context_padding_size
    if start < context_padding_size:
        context_front = start  # 前context最多到start位置
    
    # 处理结尾：如果end接近文本结尾，减少后context
    remaining_length = len(full_volume_text) - end
    context_back = context_padding_size
    if remaining_length < context_padding_size:
        context_back = remaining_length  # 后context最多到文本结尾
    
    # 使用动态的context_front和context_back来计算target_correction_area
    if context_back > 0:
        target_correction_area = current_chunk[context_front:-context_back]
    else:
        target_correction_area = current_chunk[context_front:]
    target_correction_area = normalize_whitespaces(target_correction_area)
    
    correction_prompt = build_correction_prompt(current_chunk, target_correction_area)
    
    final_decision_status, final_result_content, chosen_model, model_results = request_multi_model_correction(
        correction_prompt, target_correction_area, similarity_threshold, debug, min_models_to_agree
    )

    length_diff = 0
    if final_decision_status == 1:
        debug_print("\n" + "="*40, debug=debug)
        debug_print("✅ 测试通过：无需修改（多模型一致或无有效修改建议）", debug=debug)
        debug_print("="*40, debug=debug)
        stats['no_change'] += 1
        
    elif final_decision_status == 2:
        debug_print(f"⚠️ 测试通过（由 {chosen_model} 建议修改）", debug=debug)
        full_volume_text, length_diff = apply_chunk_correction(
            full_volume_text, current_chunk, final_result_content, start, end, context_front, context_back
        )
        stats['change'] += 1
        
    else:
        debug_print(f"❌ 测试失败：所有模型结果均不可用", debug=debug)
        stats['error'] += 1
        log_error_results(error_log_path, current_chunk, target_correction_area, model_results)
                
    return full_volume_text, length_diff

def correct_volume_text_scan(full_volume_text: str, chunk_size: int = 800, context_padding_size: int = 150, similarity_threshold: float = 0.95, debug: bool = False, error_log_path: str = "", min_models_to_agree: int = 1) -> str:
    """
    处理单卷小说的全扫描修正逻辑
    """
    start = 0
    program_start_time = time.time()
    
    stats = {'no_change': 0, 'change': 0, 'error': 0}
    base_step_size = context_padding_size + (chunk_size - 2 * context_padding_size) // 2

    # 计算大概的总迭代次数用于进度条
    estimated_total_steps = len(full_volume_text) // base_step_size + 1
    
    with tqdm(total=estimated_total_steps, desc=f"扫描窗口 {chunk_size}", unit="块") as pbar:
        while True:
            end = start + chunk_size
            if end > len(full_volume_text):
                break
                
            full_volume_text, length_diff = process_single_chunk(
                full_volume_text, start, end, context_padding_size, similarity_threshold, debug, error_log_path, stats, min_models_to_agree
            )
            
            start += base_step_size + length_diff
            
            # 更新进度条附加信息
            pbar.set_postfix(no_change=stats['no_change'], change=stats['change'], error=stats['error'])
            pbar.update(1)
            
            # 由于文本长度可能会变化，并且最后可能会提前结束，所以实际步数可能和预估不完全一致，
            # 但不影响 tqdm 的大致显示，如果超过了100%，tqdm也能自动处理。
        
    return full_volume_text

def correct_single_volume_scan(input_file_path: str, output_dir: str = "fix_story_v2", chunk_sizes: Tuple[int, ...] = (800, 700, 600, 500), similarity_threshold: float = 0.9, debug: bool = False, min_models_to_agree: int = 1):
    """
    对外暴露的接口：对单卷小说进行全卷暴力扫描的大模型纠错处理
    """
    if not os.path.exists(input_file_path):
        debug_print(f"\n[错误] 找不到输入文件: {input_file_path}", debug=debug)
        return

    filename = os.path.basename(input_file_path)
    txt_name = os.path.splitext(filename)[0]

    debug_print(f"\n🚀 开始暴力全卷扫描处理: {filename}", debug=debug)
    
    with open(input_file_path, 'r', encoding='utf-16') as f:
        full_volume_text = f.read()
    
    error_log_path = os.path.join("error_scan", txt_name, str(time.time()).replace(".", ""))
    os.makedirs(error_log_path, exist_ok=True)
    temp_dir = os.path.join(output_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    for chunk_size in chunk_sizes:
        debug_print(f"\n### {txt_name} - 当前扫描窗口大小：{chunk_size} ###", debug=debug)
        context_padding_size = chunk_size // 5
        
        full_volume_text = correct_volume_text_scan(
            full_volume_text, 
            chunk_size=chunk_size, 
            context_padding_size=context_padding_size, 
            similarity_threshold=similarity_threshold,
            debug=debug,
            error_log_path=error_log_path,
            min_models_to_agree=min_models_to_agree
        )
        
        temp_file_path = os.path.join(temp_dir, filename)
        with open(temp_file_path, 'w', encoding='utf-16') as f:
            f.write(full_volume_text)
            
    final_output_path = os.path.join(output_dir, filename)
    with open(final_output_path, 'w', encoding='utf-16') as f:
        f.write(full_volume_text)
        
    debug_print(f"\n✅ {filename} 全扫描处理完成！已保存至 {final_output_path}", debug=debug)
