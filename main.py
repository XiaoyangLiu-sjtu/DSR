import os
from src.decomposer import Decomposer
from src.structurer import Structurer
from src.repairer import Splicer, Repairer
from src.evaluator import Evaluator
from configs.config_model import get_model_config
import utils


def run_inference(benchmark, model_name, num_to_generate=1):
    cfg = get_model_config(
        model_name,
        n=num_to_generate,
        post_process_map={
            "extract_code": utils.extract_code,
            "extract_code_opt": utils.extract_code_opt,
        },
    )

    if cfg["type"] == "non_e2e":
        Structurer(cfg["path"], num_to_generate).structure(
            input_path=f"experiment/{benchmark}/nlcomp2flcomp(cl)/{benchmark}_nlcomps.json", 
            output_path=f"experiment/{benchmark}/{model_name}/flcomps_pass@{num_to_generate}.json"
        )
        Splicer().splice(
            input_path=f"experiment/{benchmark}/{model_name}/flcomps_pass@{num_to_generate}.json", 
            output_path=f"experiment/{benchmark}/{model_name}/{model_name}_pass@{num_to_generate}.json"
        )

    else:
        if cfg["type"] == "e2e":
            model = utils.LocalModel(cfg["path"], cfg["system"], cfg["sampling_params"])
        elif cfg["type"] == "e2e_api":
            model = utils.APIModel(cfg["path"], cfg["system"])

        data, informal_key = utils.data_infomal_stmt_key(benchmark)
        template_args = cfg.get("template_args", {}) 
        stmt_var_name = cfg.get("input_key_map", "informal_statement")

        task_list = []
        for item in data:
            stmt_content = item[informal_key]
            format_kwargs = {stmt_var_name: stmt_content}
            format_kwargs.update(template_args)
            input_data = cfg["instruction"].format(**format_kwargs)
            messages = model.get_messages(input_data)        
            if cfg.get("append_think", False):
                messages += "<think>"

            if cfg["type"] == "e2e_api":
                for _ in range(num_to_generate):
                    task_list.append(messages)
            else:
                task_list.append(messages)

        gen_kwargs = cfg.get("gen_kwargs", {})
        llm_outputs = model.generate_batch(task_list, **gen_kwargs)
        
        post_process_func = cfg.get("post_process")
        new_data = []
        for index, item in enumerate(data):
            if cfg["type"] == "e2e_api":
                start_idx = index * num_to_generate
                end_idx = start_idx + num_to_generate
                batch_slice = llm_outputs[start_idx : end_idx]
                raw_outputs_for_problem = [res[1] for res in batch_slice]
            else:
                raw_outputs_for_problem = llm_outputs[index]
                
            for subindex, subitem in enumerate(raw_outputs_for_problem):
                processed_stmt = post_process_func(subitem) if post_process_func else subitem
                new_data.append({
                    "index": f"{index + 1}_{subindex + 1}",
                    "informal_statement": item[informal_key],
                    "llm_output": subitem,
                    "formal_statement": processed_stmt
                })
        
        output_path = f"experiment/{benchmark}/{model_name}/{model_name}_pass@{num_to_generate}.json"
        utils.write_json(output_path, new_data)


def run_lg_repairs(benchmark, model_name):
    Repairer(benchmark, model_name).repair(f"experiment/{benchmark}/{model_name}/{model_name}_pass@{num_to_generate}.json")
    Evaluator().evaluate(benchmark, model_name, num_to_generate, repair_mode="lg")


def run_g_repairs(benchmark, model_name):
    Repairer(benchmark, model_name, only_global=True, global_repair_turns=4).repair(f"experiment/{benchmark}/{model_name}/{model_name}_pass@{num_to_generate}.json")
    Evaluator().evaluate(benchmark, model_name, num_to_generate, repair_mode="g")


if __name__ == "__main__":
    benchmarks = [
        "proverbench", "proofnet", "prime"
        "fate_x", "fate_h", "fate_m"
    ]
    models = [
        "qwen", "codex",
        "kimina", "stepfun_7b", "goedel_8b", "atf_8b",
        "stepfun_32b", "goedel_32b", "atf_32b",
        "nlstmt2flstmt", "nlstmt2flstmt(opt)", "nlstmt2flstmt(cl)", 
        "nlcomp2flcomp", "nlcomp2flcomp(opt)", "nlcomp2flcomp(cl)"
    ]
    num_to_generate = 4  # 4 For pass@4 and 1 For repair@4

    for benchmark in benchmarks:
        if not os.path.exists(f"experiment/{benchmark}/nlcomp2flcomp(cl)/{benchmark}_nlcomps.json"):
            Decomposer().decompose(benchmark, output_path=f"experiment/{benchmark}/nlcomp2flcomp(cl)/{benchmark}_nlcomps.json")

        for model_name in models:
            if not os.path.exists(f"experiment/{benchmark}/{model_name}/{model_name}_pass@{num_to_generate}.json"):
                run_inference(benchmark, model_name, num_to_generate=num_to_generate)
    
            if num_to_generate > 1:
                Evaluator().evaluate(benchmark, model_name, num_to_generate)
                continue

            if model_name == "nlcomp2flcomp(cl)" or model_name == "nlstmt2flstmt(cl)":
                run_lg_repairs(benchmark, model_name)
                run_g_repairs(benchmark, model_name)
            else:
                run_g_repairs(benchmark, model_name)