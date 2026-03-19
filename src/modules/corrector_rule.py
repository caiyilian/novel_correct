import os
import time
from typing import Tuple, List, Dict
from tqdm import tqdm

# 从本地模块导入工具函数
from src.modules.text_cleaner import normalize_whitespaces
from src.modules.utils import debug_print, find_consecutive_symbols, get_centered_story_clip
from src.modules.corrector_core import request_multi_model_correction, log_error_results, apply_chunk_correction

def build_targeted_correction_prompt(current_chunk: str, target_correction_area: str, error_char: str) -> str:
    """
    构建发给大模型的Prompt (带错误符号提示版)
    """
    correction_prompt = f"""### 强制执行规则（100%遵守，禁止任何偏离）
    1.  小说人物对话的唯一合法包裹符号，是成对的全角直角引号「」，其他任何括号、引号均不合法。
    2.  我会发给你两个片段，一个是**原始小说片段**，一个是从**原始小说片段**中间截取的**修正待检查内容**
    3.  由1.可知包裹符号会交替出现，而这段话是出现了有连续出现两次{error_char}的情况，所以一定有错误需要修正。
    4.  仅检查并修正**待检查内容**中「」的使用错误（比如用[、【、"等替代「的错误），或者缺少的情况就要补上，多余的情况就要删去。
    5.  **原始小说片段**包含了修正待检查内容，还包含了两侧的**非修正待检查内容**，**非修正待检查内容**只是作为上下文给你一个完整语境参考，以及防止截取片段把对话截断的时候让你产生误解
    6.  **绝对禁止**续写或者补全句子。如果**修正待检查内容**在句子中间断开，你的输出也必须在完全相同的地方断开。
    7.  **绝对禁止**输出任何解释性文字、前缀或后缀。只输出修正后的文本本身。
    8.  最终返回修正后的**修正待检查内容**,绝对不要输出其他额外内容。

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

def get_search_indices(error_char: str, now_index: int, last_index: int) -> List[int]:
    """
    根据冲突符号类型，智能归因返回需要搜索的中心点索引列表
    """
    if error_char == "」":
        return [now_index] # 闭符号错误只在当前位置附近
    return [now_index, last_index] # 开符号错误可能在当前或上一个相同符号附近

def process_single_targeted_chunk(
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
    处理单个目标切块，返回 (是否成功修正, 更新后的全文)
    """
    current_chunk, target_correction_area, start_idx, end_idx, context_padding_size = get_centered_story_clip(
        full_volume_text, center_index, total_length=chunk_size
    )
    
    correction_prompt = build_targeted_correction_prompt(current_chunk, target_correction_area, error_char)
    
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
            full_volume_text, current_chunk, final_result_content, start_idx, end_idx, context_padding_size
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

def correct_single_volume_rule(input_file_path: str, output_dir: str = "fix_story_v3", chunk_sizes: Tuple[int, ...] = (800, 700, 600, 500), similarity_threshold: float = 0.9, debug: bool = False, min_models_to_agree: int = 1):
    """
    对外暴露的接口：基于规则检测的精准纠错模式 (Targeted Corrector)
    只有在检测到连续的相同符号时，才会呼叫大模型。
    """
    if not os.path.exists(input_file_path):
        debug_print(f"\n[错误] 找不到输入文件: {input_file_path}", debug=debug)
        return

    filename = os.path.basename(input_file_path)
    txt_name = os.path.splitext(filename)[0]

    debug_print(f"\n🎯 开启精准定位纠错模式: {filename}", debug=debug)
    
    with open(input_file_path, 'r', encoding='utf-16') as f:
        full_volume_text = f.read()
    
    error_log_path = os.path.join("error_rule", txt_name, str(time.time()).replace(".", ""))
    os.makedirs(error_log_path, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    process_log_path = os.path.join(log_dir, f"find_error_{txt_name}.txt")
    
    with open(process_log_path, 'w', encoding="utf-8") as log_file:
        iter_count = 0
        exit_while = False
        
        # 估算进度（用文本长度）
        with tqdm(total=100, desc=f"{txt_name} 处理进度", unit="%") as pbar:
            last_progress = 0
            
            while not exit_while:
                error_char, now_index, last_index = find_consecutive_symbols(full_volume_text)
                
                if error_char is None:
                    log_file.write(f"\n#### {txt_name} 已全部修改完毕 (未发现连续符号) #####\n")
                    pbar.update(100 - last_progress)
                    debug_print(f"\n🎉 {txt_name} 已全部修改完毕 (未发现连续符号)", debug=debug)
                    break
                    
                search_indices = get_search_indices(error_char, now_index, last_index)
                chunk_success = False
                
                for chunk_size in chunk_sizes:
                    for center_index in search_indices:
                        success, full_volume_text = process_single_targeted_chunk(
                            full_volume_text, center_index, chunk_size, error_char, 
                            similarity_threshold, debug, txt_name, error_log_path, log_file, min_models_to_agree
                        )
                        
                        if success:
                            temp_file_path = os.path.join(output_dir, filename)
                            with open(temp_file_path, 'w', encoding='utf-16') as save_file:
                                save_file.write(full_volume_text)    
                            chunk_success = True
                            break # 成功修正一处，跳出搜索中心点循环
                            
                    if chunk_success:
                        break # 跳出多尺度循环，重新从头扫描全文
                    
                if not chunk_success:
                    # 所有尺度、所有中心点都尝试了依然没能成功修改
                    exit_while = True
                    debug_print(f"\n[警告] 在 {txt_name} 索引 {now_index} 附近发现死结，大模型无法修复，已中止该卷自动处理。", debug=debug)
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
    debug_print(f"\n✅ {filename} 精准纠错处理结束！已保存至 {final_output_path}", debug=debug)
