import os
import time
from typing import Tuple, List, Dict
from tqdm import tqdm

# 从本地模块导入工具函数
from src.modules.text_cleaner import normalize_whitespaces
from src.modules.utils import debug_print, find_specific_symbols, get_centered_story_clip
from src.modules.corrector_core import request_multi_model_correction, log_error_results, apply_chunk_correction

def build_bracket_correction_prompt(current_chunk: str, target_correction_area: str, error_char: str) -> str:
    """
    构建发给大模型的Prompt (专门处理 [ 和 ] 异常符号)
    """
    correction_prompt = f"""### 强制执行规则（100%遵守，禁止任何偏离）
    1.  小说人物对话的唯一合法包裹符号，是成对的全角直角引号「」，其他任何括号、引号均不合法。
    2.  我会发给你两个片段，一个是**原始小说片段**，一个是从**原始小说片段**中间截取的**修正待检查内容**。
    3.  这段话中出现了英文中括号 `{error_char}`。注意：这**大概率是不需要修改的**（可能只是正常的标点），但也有小概率是 OCR 识别错误或者是格式错误。
    4.  请你仔细甄别：仅当该符号确实是错误地包裹了对话时，才将其修正为正确的「 或 」，或者补充缺失的符号。
    5.  如果**修正待检查内容**没有需要修正的地方，直接输出"没错"2字。
    6.  **原始小说片段**包含了修正待检查内容，还包含了两侧的**非修正待检查内容**，**非修正待检查内容**只是作为上下文给你一个完整语境参考，以及防止截取片段把对话截断的时候让你产生误解。
    7.  **绝对禁止**续写或者补全句子。如果需要修改，并且**修正待检查内容**在句子中间断开，你的输出也必须在完全相同的地方断开。
    8.  **绝对禁止**输出任何解释性文字、前缀或后缀。只输出修正后的文本本身（或"没错"）。

    ---

    **原始小说片段** (仅供参考语境，不要输出):
    ```
    {current_chunk}
    ```

    ---

    **修正待检查内容** (请直接修正此内容，或输出"没错"，保持原有截断):
    ```
    {target_correction_area}
    ```
    """
    return normalize_whitespaces(correction_prompt)

def process_single_bracket_chunk(
    full_volume_text: str, 
    center_index: int, 
    chunk_size: int, 
    error_char: str, 
    similarity_threshold: float, 
    debug: bool, 
    txt_name: str, 
    error_log_path: str,
    log_file,
    min_models_to_agree: int = 1
) -> Tuple[bool, str]:
    """
    处理单个包含异常中括号的切块
    """
    current_chunk, target_correction_area, start_idx, end_idx, context_padding_size = get_centered_story_clip(
        full_volume_text, center_index, total_length=chunk_size
    )
    
    correction_prompt = build_bracket_correction_prompt(current_chunk, target_correction_area, error_char)
    
    final_decision_status, final_result_content, chosen_model, model_results = request_multi_model_correction(
        correction_prompt, target_correction_area, similarity_threshold, debug, min_models_to_agree
    )

    if final_decision_status == 1:
        debug_print("\n" + "="*40, debug=debug)
        debug_print("✅ 测试通过：无需修改（多模型一致或无有效修改建议）", debug=debug)
        log_content = f"########{txt_name}-{chunk_size}模型没有发现错误的内容########：\n{current_chunk}\n-------\n\n########待修改区域########：\n{target_correction_area}\n-------\n\n"
        log_file.write(log_content)
        return False, full_volume_text
        
    elif final_decision_status == 2:
        debug_print(f"⚠️ 测试通过（由 {chosen_model} 建议修改）", debug=debug)
        updated_text, _ = apply_chunk_correction(
            full_volume_text, current_chunk, final_result_content, start_idx, end_idx, context_padding_size, context_padding_size
        )
        return True, updated_text
        
    else:
        debug_print(f"❌ 测试失败：所有模型结果均不可用", debug=debug)
        log_content = f"########{txt_name}-{chunk_size}失败内容########：\n{current_chunk}\n-------\n\n########待修改区域########：\n{target_correction_area}\n-------\n\n"
        for res in model_results:
            log_content += f"########模型 {res['model']} (Status: {res['status']}, Ratio: {res['ratio']:.4f})########：\n{res['result']}\n"
        log_file.write(log_content)
        log_error_results(error_log_path, current_chunk, target_correction_area, model_results)
        return False, full_volume_text

def correct_single_volume_bracket(input_file_path: str, output_dir: str = "fix_story_v3", chunk_sizes: Tuple[int, ...] = (800, 700, 600, 500), similarity_threshold: float = 0.9, debug: bool = False, min_models_to_agree: int = 1):
    """
    对外暴露的接口：专门定位并修复异常的英文中括号 [ 和 ]
    """
    if not os.path.exists(input_file_path):
        debug_print(f"\n[错误] 找不到输入文件: {input_file_path}", debug=debug)
        return

    filename = os.path.basename(input_file_path)
    txt_name = os.path.splitext(filename)[0]

    debug_print(f"\n🔍 开启异常中括号清缴模式 (Stage 3): {filename}", debug=debug)
    
    with open(input_file_path, 'r', encoding='utf-16') as f:
        full_volume_text = f.read()
    
    error_log_path = os.path.join("error_bracket", txt_name, str(time.time()).replace(".", ""))
    os.makedirs(error_log_path, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    process_log_path = os.path.join(log_dir, f"find_bracket_error_{txt_name}.txt")
    
    with open(process_log_path, 'w', encoding="utf-8") as log_file:
        iter_count = 0
        exit_while = False
        
        with tqdm(total=100, desc=f"{txt_name} [ ] 清理进度", unit="%") as pbar:
            last_progress = 0
            
            while not exit_while:
                error_char, now_index = find_specific_symbols(full_volume_text, target_symbols=("[", "]"))
                
                if error_char is None:
                    log_file.write(f"\n#### {txt_name} 已全部修改完毕 (未发现中括号异常) #####\n")
                    pbar.update(100 - last_progress)
                    debug_print(f"\n🎉 {txt_name} 已全部修改完毕 (未发现中括号异常)", debug=debug)
                    break
                    
                chunk_success = False
                
                for chunk_size in chunk_sizes:
                    success, full_volume_text = process_single_bracket_chunk(
                        full_volume_text, now_index, chunk_size, error_char, 
                        similarity_threshold, debug, txt_name, error_log_path, log_file, min_models_to_agree
                    )
                    
                    if success:
                        temp_file_path = os.path.join(output_dir, filename)
                        with open(temp_file_path, 'w', encoding='utf-16') as save_file:
                            save_file.write(full_volume_text)    
                        chunk_success = True
                        break # 成功修正一处，跳出多尺度循环，重新从头扫描全文
                        
                if not chunk_success:
                    # 所有尺度都尝试了依然没能成功修改，为了避免死循环，我们将这个字符暂时替换成一个不会被再次匹配的占位符（或者简单跳过，这里选择跳过并在日志中记录，实际操作中可以直接把 `[` 换成全角 `［` 来绕过死循环）
                    # 为了安全起见，这里我们将这个导致死结的括号替换为全角括号，防止死循环
                    debug_print(f"\n[警告] 在 {txt_name} 索引 {now_index} 附近发现死结，大模型无法修复。已将其临时替换为全角以跳过死循环。", debug=debug)
                    safe_char = "［" if error_char == "[" else "］"
                    full_volume_text = full_volume_text[:now_index] + safe_char + full_volume_text[now_index+1:]
                    continue
                    
                iter_count += 1
                current_progress = int((now_index / len(full_volume_text)) * 100)
                if current_progress > last_progress:
                    pbar.update(current_progress - last_progress)
                    last_progress = current_progress
                
                pbar.set_postfix(iter=iter_count, issue_at=f"{current_progress}%")

    final_output_path = os.path.join(output_dir, filename)
    with open(final_output_path, 'w', encoding='utf-16') as save_file:
        save_file.write(full_volume_text)    
    debug_print(f"\n✅ {filename} 异常中括号清理结束！已保存至 {final_output_path}", debug=debug)
