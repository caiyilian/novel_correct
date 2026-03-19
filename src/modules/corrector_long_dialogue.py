import os
import time
from typing import Tuple, List, Dict
from tqdm import tqdm

# 从本地模块导入工具函数
from src.modules.text_cleaner import normalize_whitespaces
from src.modules.utils import debug_print, get_centered_story_clip, extract_all_dialogues, get_top_k_longest_dialogues
from src.modules.corrector_core import request_multi_model_correction, log_error_results, apply_chunk_correction

def build_long_dialogue_prompt(current_chunk: str, target_correction_area: str) -> str:
    """
    构建发给大模型的Prompt (专门处理可能由于符号缺失导致被错误合并的超长对话)
    """
    correction_prompt = f"""### 深度校验规则（100%遵守，禁止任何偏离）
    1.  我会发给你两个片段，一个是**原始小说片段**，一个是从中截取的**修正待检查内容**（一段超长的人物对话）。
    2.  目前这段**修正待检查内容**被首尾的「」包裹，看似是一段完整的对话。但是它**非常长**！
    3.  我们严重怀疑在这段超长对话的内部，**缺失了闭符号」和开符号「**，导致原本属于【对话A】+【旁白/动作描写】+【对话B】的结构，被错误地合并成了一整段巨大的对话。
    4.  **你的任务**：仔细阅读这段**修正待检查内容**，判断其内部是否存在明显的“非对话内容（如旁白、动作、心理描写等）”。
    5.  如果存在，请在合适的位置**补全缺失的「或」**，将其正确地拆分。例如，将 `「你好啊。他走上前来。你好。」` 修正为 `「你好啊。」他走上前来。「你好。」`。
    6.  如果确认为一段连续的完整对话，则无需任何修改，原样输出即可。
    7.  **绝对禁止**修改除了「」之外的任何文字内容、换行、空格！
    8.  最终只返回处理后的**修正待检查内容**, 绝对不要输出解释性文字。

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

def process_single_long_dialogue(
    full_volume_text: str, 
    dialogue_info: Dict, 
    chunk_size: int, 
    similarity_threshold: float, 
    debug: bool, 
    txt_name: str, 
    error_log_path: str,
    log_file,
    min_models_to_agree: int = 2
) -> Tuple[bool, str]:
    """
    处理单个超长对话切块
    """
    center_index = dialogue_info['center_index']
    
    # 动态调整 chunk_size，确保至少能包裹住整个对话，并向外延伸一定上下文
    actual_chunk_size = max(chunk_size, dialogue_info['length'] + 300)
    
    current_chunk, target_correction_area, start_idx, end_idx, context_padding_size = get_centered_story_clip(
        full_volume_text, center_index, total_length=actual_chunk_size
    )
    
    correction_prompt = build_long_dialogue_prompt(current_chunk, target_correction_area)
    
    final_decision_status, final_result_content, chosen_model, model_results = request_multi_model_correction(
        correction_prompt, target_correction_area, similarity_threshold, debug, min_models_to_agree
    )

    if final_decision_status == 1:
        debug_print("\n" + "="*40, debug=debug)
        debug_print(f"✅ 测试通过：长对话确认合规，无需拆分 (长度: {dialogue_info['length']})", debug=debug)
        log_content = f"########{txt_name}-合规长对话(未拆分)########：\n{target_correction_area}\n-------\n\n"
        log_file.write(log_content)
        return False, full_volume_text
        
    elif final_decision_status == 2:
        debug_print(f"⚠️ 发现合并异常！由 {chosen_model} 建议拆分", debug=debug)
        updated_text, length_diff = apply_chunk_correction(
            full_volume_text, current_chunk, final_result_content, start_idx, end_idx, context_padding_size, context_padding_size
        )
        log_content = f"########{txt_name}-成功拆分长对话########：\n[原内容]:\n{target_correction_area}\n\n[修改后]:\n{final_result_content}\n-------\n\n"
        log_file.write(log_content)
        return True, updated_text
        
    else:
        debug_print(f"❌ 测试失败：所有模型均无法给出有效的拆分建议", debug=debug)
        log_content = f"########{txt_name}-拆分失败########：\n{target_correction_area}\n-------\n\n"
        log_file.write(log_content)
        log_error_results(error_log_path, current_chunk, target_correction_area, model_results)
        return False, full_volume_text

def correct_single_volume_long_dialogue(input_file_path: str, output_dir: str = "fix_story_v5", chunk_sizes: Tuple[int, ...] = (1200, 1000, 800), similarity_threshold: float = 0.9, debug: bool = False, min_models_to_agree: int = 2, top_k: int = 10):
    """
    对外暴露的接口：专门针对文本中最长的 Top K 个对话进行深度校验，看是否需要拆分
    """
    if not os.path.exists(input_file_path):
        debug_print(f"\n[错误] 找不到输入文件: {input_file_path}", debug=debug)
        return

    filename = os.path.basename(input_file_path)
    txt_name = os.path.splitext(filename)[0]

    debug_print(f"\n📏 开启超长对话深度校验模式 (Stage 5): {filename}", debug=debug)
    
    with open(input_file_path, 'r', encoding='utf-16') as f:
        full_volume_text = f.read()
        
    # 提取所有对话并获取最长的前 K 个
    all_dialogues = extract_all_dialogues(full_volume_text)
    if not all_dialogues:
        debug_print(f"\n[警告] 未能在 {txt_name} 中提取到任何对话！", debug=debug)
        return
        
    top_dialogues = get_top_k_longest_dialogues(all_dialogues, k=top_k)
    
    # 【核心防御机制：倒序处理】
    # 将对话按照在文中出现的绝对索引从后往前排序。
    # 这样修改排在后面的文本，绝对不会影响排在前面的文本的绝对索引！
    top_dialogues.sort(key=lambda x: x['start_index'], reverse=True)
    
    error_log_path = os.path.join("error_long_dialogue", txt_name, str(time.time()).replace(".", ""))
    os.makedirs(error_log_path, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    process_log_path = os.path.join(log_dir, f"long_dialogue_check_{txt_name}.txt")
    
    with open(process_log_path, 'w', encoding="utf-8") as log_file:
        with tqdm(total=len(top_dialogues), desc=f"{txt_name} 长对话校验进度", unit="个") as pbar:
            for idx, dialogue_info in enumerate(top_dialogues):
                debug_print(f"\n--- 正在处理第 {idx+1}/{len(top_dialogues)} 个长对话 (倒序)，原长度: {dialogue_info['length']} ---", debug=debug)
                
                chunk_success = False
                # 尝试不同的上下文窗口大小，长对话需要更大的窗口
                for chunk_size in chunk_sizes:
                    success, full_volume_text = process_single_long_dialogue(
                        full_volume_text, dialogue_info, chunk_size, 
                        similarity_threshold, debug, txt_name, error_log_path, log_file, min_models_to_agree
                    )
                    
                    if success:
                        chunk_success = True
                        break # 成功拆分一处，跳出多尺度循环
                        
                pbar.update(1)

    final_output_path = os.path.join(output_dir, filename)
    with open(final_output_path, 'w', encoding='utf-16') as save_file:
        save_file.write(full_volume_text)    
    debug_print(f"\n✅ {filename} 超长对话深度校验结束！已保存至 {final_output_path}", debug=debug)