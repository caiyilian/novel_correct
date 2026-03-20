import os
import argparse
from src.modules.corrector_scan import correct_single_volume_scan
from src.modules.corrector_rule import correct_single_volume_rule
from src.modules.corrector_bracket import correct_single_volume_bracket
from src.modules.corrector_long_dialogue import correct_single_volume_long_dialogue
from src.main_preprocess import PreprocessPipeline
from src.modules.utils import debug_print

def run_preprocessing(ori_dir: str, proc_dir: str, log_dir: str, debug: bool):
    debug_print("\n" + "="*50, debug=debug)
    debug_print("🚀 开始执行预处理模块...", debug=debug)
    debug_print("="*50, debug=debug)
    pipeline = PreprocessPipeline(ori_dir, proc_dir, log_dir)
    success = pipeline.run()
    if not success:
        debug_print("⚠️ 预处理过程中出现错误，请检查日志。", debug=debug)
    else:
        debug_print("✅ 预处理完成！\n", debug=debug)

def parse_args():
    parser = argparse.ArgumentParser(
        description="📖 小说自动纠错系统 - 多模型双模式处理程序\n\n"
                    "[系统配置信息]\n"
                    "如果需要修改大模型 IP 地址或调整使用的模型列表，\n"
                    "请前往修改配置文件: `src/config/settings.py`",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # 核心执行参数
    parser.add_argument("-i", "--input_file", type=str, default=r"data/processed_story/第1卷.txt",
                        help="指定要处理的单卷文件路径。在 --batch 模式下该参数被忽略 (默认: data/processed_story/第1卷.txt)")
    
    parser.add_argument("--batch", action="store_true",
                        help="开启批量模式：自动扫描 data/processed_story/ 目录下的所有 .txt 文件并进行处理")
    
    parser.add_argument("--preprocess_all", action="store_true",
                        help="一键批量预处理：自动扫描 data/ori_story/ 目录下的所有文件并全部进行预处理")
    
    parser.add_argument("--force_preprocess", action="store_true",
                        help="是否强制重新进行预处理。如果输入文件已存在，使用此参数将重新预处理 (默认: False)")
    
    # 预处理相关路径配置
    parser.add_argument("--ori_dir", type=str, default=r"data/ori_story",
                        help="原始小说存放目录 (默认: data/ori_story)")
    
    parser.add_argument("--proc_dir", type=str, default=r"data/processed_story",
                        help="预处理后小说存放目录 (默认: data/processed_story)")
    
    parser.add_argument("--log_dir", type=str, default=r"logs",
                        help="预处理日志存放目录 (默认: logs)")
    
    # 核心算法参数
    parser.add_argument("-o", "--output_dir", type=str, default="fix_story_v2",
                        help="修正后小说的保存目标文件夹 (默认: fix_story_v2)")
    
    parser.add_argument("--chunk_sizes", type=int, nargs='+', default=[800, 700, 600, 500],
                        help="多尺度扫描的窗口大小，依次尝试，越靠后越细致 (默认: 800 700 600 500)")
    
    parser.add_argument("--similarity_threshold", type=float, default=0.9,
                        help="防幻觉阈值，0.9表示大模型输出必须和原文有90%%以上相似度才接受 (默认: 0.9)")
    
    parser.add_argument("--debug", action="store_true", default=False,
                        help="是否在终端输出详细执行信息和每一次大模型的对比结果 (默认: False)")
    
    parser.add_argument("--min_agree", type=int, default=1,
                        help="至少需要多少个模型得出相同的(或可接受的)修改才能进行修正。\n"
                             "如果该值大于 FALLBACK_MODELS 的总数，程序会自动将其限制为模型总数 (默认: 1)")
    
    parser.add_argument("--long_dialogue_top_k", type=int, default=10,
                        help="[Stage 5专用] 每卷抽查最长的前几个对话进行拆分深度校验 (默认: 10)")
    
    parser.add_argument("--long_dialogue_min_agree", type=int, default=2,
                        help="[Stage 5专用] 拆分长对话需要多少个模型达成共识 (默认: 2)")
    
    # 运行模式选择
    parser.add_argument("--pipeline", action="store_true",
                        help="开启流水线模式：自动依次执行 v1(暴力扫描) -> v2(规则修复) -> v3(异常中括号) -> v4(规则兜底) -> v5(长对话拆分)。\n"
                             "开启此模式后，-o 和 --stage 参数将被忽略。")
                             
    parser.add_argument("--stage", type=int, choices=[1, 2, 3, 4, 5], default=None,
                        help="单独执行某个阶段 (1: 暴力扫描, 2: 规则修复, 3: 异常中括号, 4: 规则兜底, 5: 长对话拆分)。\n"
                             "如果未开启 --pipeline，且未指定 --stage，则需检查是否指定了其他模式参数。")
    
    return parser.parse_args()

def process_single_file(input_file: str, args, my_chunk_sizes, OUTPUT_DIR_V1, OUTPUT_DIR_V2, OUTPUT_DIR_V3, OUTPUT_DIR_V4, OUTPUT_DIR_V5):
    debug_print(f"\n=============================================", debug=args.debug)
    debug_print(f"即将开始处理文件: {input_file}", debug=args.debug)
    debug_print(f"使用的上下文窗口: {my_chunk_sizes}", debug=args.debug)
    debug_print(f"当前的防幻觉阈值: {args.similarity_threshold}", debug=args.debug)
    debug_print(f"要求达成共识的模型数量: {args.min_agree}", debug=args.debug)
    debug_print(f"=============================================\n", debug=args.debug)
    
    filename = os.path.basename(input_file)
    
    # -------------------------------
    # 流水线执行逻辑
    # -------------------------------
    if args.pipeline:
        debug_print(f"🌟 启动完整纠错流水线 (Pipeline Mode) 🌟\n", debug=args.debug)
        
        # --- Stage 1: 暴力扫描与规则交替 ---
        debug_print(f"▶️ [Stage 1] 执行全局暴力扫描与规则修复交织模式...", debug=True)
        
        current_input_for_stage1 = input_file
        
        for size in my_chunk_sizes:
            debug_print(f"\n" + "-"*40, debug=True)
            debug_print(f"🌀 [Stage 1] 启动单窗口暴力扫描 (chunk_size: {size})", debug=True)
            
            # 单窗口扫描
            correct_single_volume_scan(
                input_file_path=current_input_for_stage1,
                output_dir=OUTPUT_DIR_V1,
                chunk_sizes=(size,),  # 每次只传一个尺寸
                similarity_threshold=args.similarity_threshold,
                debug=args.debug,
                min_models_to_agree=args.min_agree
            )
            
            stage1_output = os.path.join(OUTPUT_DIR_V1, filename)
            if not os.path.exists(stage1_output):
                debug_print(f"\n❌ [Stage 1] 扫描产出文件 {stage1_output} 不存在，流水线终止！", debug=True)
                return
                
            debug_print(f"🌀 [Stage 1] 紧跟辅助规则修复，清扫遗漏死角...", debug=True)
            
            # 紧跟规则修复，开启防死结短路监控 (max_stagnant_iters=10)
            correct_single_volume_rule(
                input_file_path=stage1_output,
                output_dir=OUTPUT_DIR_V1, # 覆盖回 V1 文件夹
                chunk_sizes=my_chunk_sizes,
                similarity_threshold=args.similarity_threshold,
                debug=args.debug,
                min_models_to_agree=args.min_agree,
                max_stagnant_iters=10 # 连续10次进度不推进则跳出
            )
            
            # 下一个 size 的扫描基于本次规则修复的输出
            current_input_for_stage1 = stage1_output
        
        # --- Stage 2: 严格规则扫描 (一票否决) ---
        debug_print(f"\n▶️ [Stage 2] 执行规则交替修复 (严格模式)...", debug=True)
        success = correct_single_volume_rule(
            input_file_path=stage1_output,  # 这里的输入是 Stage 1 最终的输出
            output_dir=OUTPUT_DIR_V2,
            chunk_sizes=my_chunk_sizes,
            similarity_threshold=args.similarity_threshold,
            debug=args.debug,
            min_models_to_agree=args.min_agree,
            max_stagnant_iters=10 # 严格模式，触发则彻底终止流水线
        )
        
        if not success:
            debug_print(f"\n❌ [Stage 2] 规则扫描陷入死结或连续 10 次未推进进度！", debug=True)
            debug_print(f"❌ [Stage 2] 判定本卷存在不可调和的逻辑错误，后续 Stage (3/4/5) 失去意义，流水线强制终止！", debug=True)
            return
        
        # --- Stage 3: 异常中括号清理 ---
        stage2_output = os.path.join(OUTPUT_DIR_V2, filename)
        if not os.path.exists(stage2_output):
            debug_print(f"\n❌ Stage 2 产出文件 {stage2_output} 不存在，流水线终止！", debug=True)
            return
            
        debug_print(f"\n▶️ [Stage 3] 执行异常中括号 [ ] 清理...", debug=True)
        correct_single_volume_bracket(
            input_file_path=stage2_output,  # 这里的输入是 Stage 2 的输出
            output_dir=OUTPUT_DIR_V3,
            chunk_sizes=my_chunk_sizes,
            similarity_threshold=args.similarity_threshold,
            debug=args.debug,
            min_models_to_agree=args.min_agree
        )
        
        # --- Stage 4: 最终规则兜底 ---
        stage3_output = os.path.join(OUTPUT_DIR_V3, filename)
        if not os.path.exists(stage3_output):
            debug_print(f"\n❌ Stage 3 产出文件 {stage3_output} 不存在，流水线终止！", debug=True)
            return
            
        debug_print(f"\n▶️ [Stage 4] 执行最终规则交替兜底修复...", debug=True)
        correct_single_volume_rule(
            input_file_path=stage3_output,  # 这里的输入是 Stage 3 的输出
            output_dir=OUTPUT_DIR_V4,
            chunk_sizes=my_chunk_sizes,
            similarity_threshold=args.similarity_threshold,
            debug=args.debug,
            min_models_to_agree=args.min_agree
        )
        
        # --- Stage 5: 超长对话深度校验 (长对话拆分) ---
        stage4_output = os.path.join(OUTPUT_DIR_V4, filename)
        if not os.path.exists(stage4_output):
            debug_print(f"\n❌ Stage 4 产出文件 {stage4_output} 不存在，流水线终止！", debug=True)
            return
            
        debug_print(f"\n▶️ [Stage 5] 执行超长对话深度校验与拆分...", debug=True)
        correct_single_volume_long_dialogue(
            input_file_path=stage4_output,  # 这里的输入是 Stage 4 的输出
            output_dir=OUTPUT_DIR_V5,
            chunk_sizes=my_chunk_sizes,
            similarity_threshold=args.similarity_threshold,
            debug=args.debug,
            min_models_to_agree=args.long_dialogue_min_agree,
            top_k=args.long_dialogue_top_k
        )
        
        debug_print(f"\n🎉 流水线执行完毕！最终究极完成版保存在: {os.path.join(OUTPUT_DIR_V5, filename)}", debug=True)

    # -------------------------------
    # 单步执行逻辑
    # -------------------------------
    elif args.stage == 1:
        debug_print(f"▶️ [单步执行] Stage 1: 全局暴力扫描", debug=True)
        correct_single_volume_scan(
            input_file_path=input_file,
            output_dir=args.output_dir,
            chunk_sizes=my_chunk_sizes,
            similarity_threshold=args.similarity_threshold,
            debug=args.debug,
            min_models_to_agree=args.min_agree
        )
    elif args.stage == 2:
        debug_print(f"▶️ [单步执行] Stage 2: 规则交替修复", debug=True)
        correct_single_volume_rule(
            input_file_path=input_file,
            output_dir=args.output_dir,
            chunk_sizes=my_chunk_sizes,
            similarity_threshold=args.similarity_threshold,
            debug=args.debug,
            min_models_to_agree=args.min_agree
        )
    elif args.stage == 3:
        debug_print(f"▶️ [单步执行] Stage 3: 异常中括号修复", debug=True)
        correct_single_volume_bracket(
            input_file_path=input_file,
            output_dir=args.output_dir,
            chunk_sizes=my_chunk_sizes,
            similarity_threshold=args.similarity_threshold,
            debug=args.debug,
            min_models_to_agree=args.min_agree
        )
    elif args.stage == 4:
        debug_print(f"▶️ [单步执行] Stage 4: 最终规则兜底", debug=True)
        correct_single_volume_rule(
            input_file_path=input_file,
            output_dir=args.output_dir,
            chunk_sizes=my_chunk_sizes,
            similarity_threshold=args.similarity_threshold,
            debug=args.debug,
            min_models_to_agree=args.min_agree
        )
    elif args.stage == 5:
        debug_print(f"▶️ [单步执行] Stage 5: 超长对话深度校验与拆分", debug=True)
        correct_single_volume_long_dialogue(
            input_file_path=input_file,
            output_dir=args.output_dir,
            chunk_sizes=my_chunk_sizes,
            similarity_threshold=args.similarity_threshold,
            debug=args.debug,
            min_models_to_agree=args.long_dialogue_min_agree,
            top_k=args.long_dialogue_top_k
        )
    else:
        debug_print("⚠️ 未指定运行模式。请使用 --pipeline 运行完整流水线，或使用 --stage 1/2 单独运行某一步。", debug=True)
        debug_print("💡 查看帮助信息: python main.py -h", debug=True)

def main():
    args = parse_args()
    
    # 将列表转换为元组以保持与原逻辑一致
    my_chunk_sizes = tuple(args.chunk_sizes)
    
    # 从配置导入流水线目录
    from src.config.settings import OUTPUT_DIR_V1, OUTPUT_DIR_V2, OUTPUT_DIR_V3, OUTPUT_DIR_V4, OUTPUT_DIR_V5

    # -------------------------------
    # 批量预处理逻辑 (--preprocess_all)
    # -------------------------------
    if args.preprocess_all:
        debug_print(f"\n=============================================", debug=True)
        debug_print(f"🚀 开始执行全局批量预处理模式...", debug=True)
        debug_print(f"=============================================", debug=True)
        
        if not os.path.exists(args.ori_dir):
            debug_print(f"❌ 原始文件目录不存在: {args.ori_dir}", debug=True)
            return
            
        ori_files = [f for f in os.listdir(args.ori_dir) if f.endswith('.txt')]
        if not ori_files:
            debug_print(f"⚠️ 警告: 未在 {args.ori_dir} 中找到任何 .txt 文件！", debug=True)
            return
            
        debug_print(f"共发现 {len(ori_files)} 个原始文件，开始预处理...\n", debug=True)
        run_preprocessing(args.ori_dir, args.proc_dir, args.log_dir, args.debug)
        debug_print(f"\n✅ 批量预处理全部完成！", debug=True)
        
        # 如果只执行了 --preprocess_all，没有其他指令，则直接返回
        if not args.batch and not args.pipeline and args.stage is None:
            return

    # -------------------------------
    # 批量纠错流水线逻辑 (--batch)
    # -------------------------------
    if args.batch:
        debug_print(f"\n=============================================", debug=True)
        debug_print(f"🌟 启动批量纠错模式 (Batch Mode) 🌟", debug=True)
        debug_print(f"=============================================", debug=True)
        
        if not os.path.exists(args.proc_dir):
            debug_print(f"\n❌ 预处理目录不存在: {args.proc_dir}", debug=True)
            return
            
        proc_files = [f for f in os.listdir(args.proc_dir) if f.endswith('.txt')]
        
        # 前置拦截与警告机制
        if not proc_files:
            debug_print(f"\n⚠️ 警告：未在 `{args.proc_dir}` 中找到任何预处理后的小说！", debug=True)
            debug_print(f"💡 请确保已将你的原始小说文件放入 `{args.ori_dir}` 目录下，", debug=True)
            debug_print(f"💡 并先执行批量预处理：python main.py --preprocess_all", debug=True)
            return
        
        try: # 排不排序都行
            proc_files = sorted(proc_files,key=lambda x:int(x[1:-5]))
        except:
            pass
        
        debug_print(f"共发现 {len(proc_files)} 个预处理文件，准备逐一处理...\n", debug=True)
        
        for idx, filename in enumerate(proc_files, 1):
            input_file = os.path.join(args.proc_dir, filename)
            debug_print(f"\n" + "#"*60, debug=True)
            debug_print(f"📦 [Batch {idx}/{len(proc_files)}] 开始处理文件: {filename}", debug=True)
            debug_print(f"#"*60, debug=True)
            
            process_single_file(
                input_file, args, my_chunk_sizes, 
                OUTPUT_DIR_V1, OUTPUT_DIR_V2, OUTPUT_DIR_V3, OUTPUT_DIR_V4, OUTPUT_DIR_V5
            )
            
        debug_print(f"\n🎉🎉🎉 所有批量任务处理完毕！", debug=True)
        return

    # -------------------------------
    # 单文件预处理与调度逻辑 (默认模式)
    # -------------------------------
    if "processed_story" not in args.input_file.replace("\\", "/"):
        debug_print(f"\n⚠️ [警告] 发现您指定的输入文件 '{args.input_file}' 似乎并非来自预处理文件夹 (processed_story)。", debug=True)
        debug_print("⚠️ 建议您先使用预处理功能清洗原始文本，以保证后续纠错流水线的最佳效果！\n", debug=True)
    else:
        if not os.path.exists(args.input_file):
            debug_print(f"\n⚠️ 未找到目标文件: {args.input_file}", debug=args.debug)
            debug_print("自动启动预处理流程...", debug=args.debug)
            run_preprocessing(args.ori_dir, args.proc_dir, args.log_dir, args.debug)
        elif args.force_preprocess:
            debug_print(f"\n🔔 检测到 force_preprocess=True，将重新执行预处理...", debug=args.debug)
            run_preprocessing(args.ori_dir, args.proc_dir, args.log_dir, args.debug)
        else:
            debug_print(f"\n✅ 目标文件已存在，跳过预处理阶段。", debug=args.debug)

    if not os.path.exists(args.input_file):
        debug_print(f"\n❌ 预处理后仍未找到文件: {args.input_file}，程序退出。请检查源文件夹 {args.ori_dir} 是否存在对应文件。", debug=args.debug)
        return

    process_single_file(
        args.input_file, args, my_chunk_sizes, 
        OUTPUT_DIR_V1, OUTPUT_DIR_V2, OUTPUT_DIR_V3, OUTPUT_DIR_V4, OUTPUT_DIR_V5
    )

if __name__ == "__main__":
    main()
