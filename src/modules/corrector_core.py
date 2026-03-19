import os
import time
from typing import Tuple, List, Dict

from src.config.settings import FALLBACK_MODELS
from src.modules.llm_client import call_ollama_api
from src.modules.text_cleaner import normalize_whitespaces, extract_and_clean_llm_output
from src.modules.utils import debug_print, calculate_similarity, has_meaningful_changes

def evaluate_model_result(target_correction_area: str, result: str, similarity_threshold: float) -> Tuple[int, float]:
    """
    评估模型输出的结果状态
    返回: (状态码, 相似度)
    状态码: 1=无修改, 2=可接受修改, 3=丢弃
    """
    if not has_meaningful_changes(target_correction_area, result):
        return 1, 1.0
        
    ratio = calculate_similarity(target_correction_area, result)
    
    if ratio >= similarity_threshold:
        # 开头和结尾的字符一定要一样，防止截断或幻觉加词
        if target_correction_area[0] == result[0] and target_correction_area[-1] == result[-1]:
            return 2, ratio
            
    return 3, ratio

def request_multi_model_correction(correction_prompt: str, target_correction_area: str, similarity_threshold: float, debug: bool, min_models_to_agree: int = 1) -> Tuple[int, str, str, List[Dict]]:
    """
    请求多模型进行修正兜底
    返回: (最终决策状态, 最终结果内容, 选用的模型名, 所有模型的运行记录)
    """
    model_results = []
    
    # 强制校验并修正 min_models_to_agree，确保它不超过配置的模型总数
    actual_min_agree = min(min_models_to_agree, len(FALLBACK_MODELS))
    
    agreed_count = 0
    
    for model_name in FALLBACK_MODELS:
        try:
            raw_result = call_ollama_api(correction_prompt, model_name=model_name)
            result = extract_and_clean_llm_output(target_correction_area, raw_result)
            result = normalize_whitespaces(result)
            
            status, ratio = evaluate_model_result(target_correction_area, result, similarity_threshold)
            
            model_results.append({
                'model': model_name,
                'result': result,
                'status': status,
                'ratio': ratio,
                'raw_result': raw_result
            })
            
            if status == 2:
                agreed_count += 1
                # 如果达到指定的同意模型数量，则跳出兜底循环
                if agreed_count >= actual_min_agree:
                    break
                
        except Exception as e:
            debug_print(f"模型 {model_name} 调用失败: {e}", debug=debug)
            continue

    # 决策逻辑
    valid_changes = [res for res in model_results if res['status'] == 2]
    # 只有当提供可接受修改的模型数量达到要求时，才最终采纳（取其中第一个可接受的修改结果）
    if len(valid_changes) >= actual_min_agree:
        best_choice = valid_changes[0]
        return 2, best_choice['result'], best_choice['model'], model_results
        
    if any(res['status'] == 1 for res in model_results):
        return 1, "", "", model_results
        
    return 3, "", "", model_results

def log_error_results(error_log_path: str, current_chunk: str, target_correction_area: str, model_results: List[Dict]):
    """
    记录所有模型都失败的错误日志
    """
    if not error_log_path:
        return
        
    log_content = f"########完整内容########：\n{current_chunk}\n-------\n\n########待修改区域########：\n{target_correction_area}\n-------\n\n"
    for res in model_results:
        log_content += f"########模型 {res['model']} (Status: {res['status']}, Ratio: {res['ratio']:.4f})########：\n{res['result']}\n"
    
    log_filename = os.path.join(error_log_path, f"{str(time.time()).replace('.', '')}.txt")
    with open(log_filename, 'w', encoding='utf-8') as log_file:
        log_file.write(log_content)

def apply_chunk_correction(full_volume_text: str, current_chunk: str, final_result_content: str, start: int, end: int, context_padding_size: int) -> Tuple[str, int]:
    """
    将模型修改后的内容融合回原文，并返回更新后的全文和步长增量
    """
    fixed_chunk = current_chunk[:context_padding_size] + final_result_content + current_chunk[-context_padding_size:]
    updated_text = full_volume_text[:start] + fixed_chunk + full_volume_text[end:]
    length_diff = len(fixed_chunk) - len(current_chunk)
    return updated_text, length_diff
