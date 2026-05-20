import configs.config_prompt as config_prompt
import re
import utils


class Compiler:
    def compile(self, input_path, header_needed=False):
        data = utils.read_json(input_path)
        new_data = []
        for item in data:
            if header_needed:
                new_data.append("import Mathlib\n"+item["formal_statement"])
            else:
                new_data.append(item["formal_statement"])
        result_list = utils.lean4_scheduler(new_data)["results"]

        for index, result in enumerate(result_list):
            try:
                message_list = result["response"]["messages"]
                is_valid = "True"
                for item in message_list:
                    if item["severity"] == "error":
                        is_valid = "False"
                        break
                data[index]["compile_result"] = is_valid
            except:
                data[index]["compile_result"] = "False"
        utils.write_json(input_path, data)


class LeanScorer:
    def __init__(self):
        self.leanscore_stage1_system, self.leanscore_stage1_instruction = config_prompt.evaluation_prompt_leanscore_stage1()
        self.leanscore_stage2_system, self.leanscore_stage2_instruction = config_prompt.evaluation_prompt_leanscore_stage2()
        self.leanscore_stage1_model = utils.APIModel("deepseek-v3.2", self.leanscore_stage1_system)
        self.leanscore_stage2_model = utils.APIModel("deepseek-v3.2", self.leanscore_stage2_system)

    def calculate_fuzzy_measure(self, indices_in_subset, all_labels):
        if not indices_in_subset:
            return 0.0
        
        n = len(all_labels)
        subset_labels = [all_labels[i] for i in indices_in_subset]
        count_A = subset_labels.count("A")
        count_B = subset_labels.count("B")
        count_C = subset_labels.count("C")
        
        if count_C > 0:
            return 0.0
        if len(indices_in_subset) == n and count_A == n:
            return 1.0
            
        base_ratio = count_A / n
        if count_B >= 2:
            penalty = 1.0 - 0.2 * count_B
            return base_ratio * max(penalty, 0.0)
        if count_B == 1:
            return base_ratio * 0.9
        return base_ratio

    def sugeno_integral(self, labels):
        if "C" in labels:
            return 0.0
        
        mapping = {"A": 1.0, "B": 0.5, "C": 0.0}
        try:
            f_values = [mapping[label] for label in labels]
        except KeyError:
            return 0.0
            
        n = len(f_values)
        if n == 0:
            return 0.0
            
        unique_thresholds = sorted(list(set(f_values)), reverse=True)         
        max_score = 0.0
        for alpha in unique_thresholds:
            if alpha == 0: 
                continue                
            M_indices = [i for i, val in enumerate(f_values) if val >= alpha]
            mu_val = self.calculate_fuzzy_measure(M_indices, labels)
            current_score = min(alpha, mu_val)
            if current_score > max_score:
                max_score = current_score
        return max_score

    def parse_llm_labels(self, llm_output):
        matches = re.findall(r"\\box(?:ed)?[\{\(](.*?)[\}\)]", llm_output, re.IGNORECASE)
        standardized_labels = []
        for m in matches:
            content = m.strip().lower()
            if "perfectly match" in content:
                standardized_labels.append("A")
            elif "minor inconsistency" in content:
                standardized_labels.append("B")
            elif "major inconsistency" in content:
                standardized_labels.append("C")
            else:
                standardized_labels.append("C")
        return standardized_labels

    def leanscorer(self, input_path, alpha=0.6):
        data = utils.read_json(input_path)

        task_list_decomposition = []
        target_indices = []
        for i, item in enumerate(data):
            compile_res = str(item.get("compile_result", "False"))
            if compile_res.lower() != "false":
                informal_statement = item["informal_statement"]
                input_data = self.leanscore_stage1_instruction.format(
                    informal_statement=informal_statement
                )
                messages = self.leanscore_stage1_model.get_messages(input_data)
                task_list_decomposition.append(messages)
                target_indices.append(i)
            else:
                data[i]["leanscorer_decomposition_output"] = ""
                data[i]["leanscorer_evaluation_output"] = ""
                data[i]["leanscorer_score"] = 0.0
                data[i]["leanscorer_result"] = False

        if task_list_decomposition:
            llm_outputs_decomposition = self.leanscore_stage1_model.generate_batch(
                task_list_decomposition, desc="LeanScorer Decomposition", max_workers=30
            )
            
            task_list_evaluation = []
            for idx, (task, decomposed_output, _, _) in zip(target_indices, llm_outputs_decomposition):
                data[idx]["leanscorer_decomposition_output"] = decomposed_output                
                informal_statement = data[idx]["informal_statement"]
                formal_statement = data[idx]["formal_statement"]
                input_data = self.leanscore_stage2_instruction.format(
                    informal_statement=informal_statement,
                    formal_statement=formal_statement,
                    math_conditions=decomposed_output
                )
                messages = self.leanscore_stage2_model.get_messages(input_data)
                task_list_evaluation.append(messages)

            if task_list_evaluation:
                llm_outputs_evaluation = self.leanscore_stage2_model.generate_batch(
                    task_list_evaluation, desc="LeanScorer Evaluation", max_workers=30
                )
                for idx, (task, evaluation_output, _, _) in zip(target_indices, llm_outputs_evaluation):
                    labels = self.parse_llm_labels(evaluation_output)
                    if not labels:
                        final_score = 0.0
                        is_pass = False
                    else:
                        final_score = self.sugeno_integral(labels)
                        is_pass = final_score >= alpha
                    data[idx]["leanscorer_evaluation_output"] = evaluation_output
                    data[idx]["leanscorer_score"] = final_score
                    data[idx]["leanscorer_result"] = is_pass
        utils.write_json(input_path, data)


class Evaluator:
    def calculate_evaluation_results(self, json_file_path, output_md_path):    
        md_content = []
        md_content.append("# Evaluation Statistics Report\n")
        
        data = utils.read_json(json_file_path)        
        problem_status = {}        

        for item in data:
            idx_str = str(item.get("index", ""))
            if "_" in idx_str:
                base_id = idx_str.split('_')[0]
            else:
                base_id = idx_str
            
            if base_id not in problem_status:
                problem_status[base_id] = {
                    "compile": False,
                    "leanscorer": False,
                    "llmjudge": False
                }
            
            compile_val_str = str(item.get("compile_result", "False"))
            is_compile_success = compile_val_str.lower() != "false"
            lean_res = item.get("leanscorer_result")
            is_lean_success = (lean_res is True)

            if is_compile_success:
                problem_status[base_id]["compile"] = True
            if is_lean_success:
                problem_status[base_id]["leanscorer"] = True

        total_unique_problems = len(problem_status) 
        solved_counts = {
            "compile": 0,
            "leanscorer": 0,
        }
        
        for pid, status in problem_status.items():
            if status["compile"]:
                solved_counts["compile"] += 1
            if status["leanscorer"]:
                solved_counts["leanscorer"] += 1

        def calc_ratio(count, total):
            return f"{(count / total * 100):.2f}%" if total > 0 else "0.0%"

        md_content.append("## Evaluation Metrics (Pass@k / Solve Rate)\n")        
        md_content.append(f"**Total Unique Problems**: {total_unique_problems}")
        md_content.append(f"*(Note: A problem is considered 'Solved' if at least one of its k samples is correct)*")
        md_content.append("")
        md_content.append("| Metric | Solved Problems | Solve Rate |")
        md_content.append("| :--- | :---: | :---: |")
        md_content.append(f"| Compile Success | {solved_counts['compile']} | {calc_ratio(solved_counts['compile'], total_unique_problems)} |")
        md_content.append(f"| LeanScorer Pass | {solved_counts['leanscorer']} | {calc_ratio(solved_counts['leanscorer'], total_unique_problems)} |")
        md_content.append("")
        md_content.append("---")
        md_content.append("")

        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content))
        print(f"Report generated successfully: {output_md_path}")

    def evaluate(self, benchmark, eval_model, num_to_generate, repair_mode=None):
        if repair_mode == None:
            input_path = f"experiment/{benchmark}/{eval_model}/{eval_model}_pass@{num_to_generate}.json"
        else:
            input_path = f"experiment/{benchmark}/{eval_model}/{eval_model}_pass@{num_to_generate}_{repair_mode}.json"

        header_needed_models = ["nlstmt2flstmt", "nlstmt2flstmt(opt)", "nlstmt2flstmt(cl)", 
                                "nlcomp2flcomp", "nlcomp2flcomp(opt)", "nlcomp2flcomp(cl)"]
        header_needed = eval_model in header_needed_models
        
        Compiler().compile(input_path, header_needed=header_needed)
        LeanScorer().leanscorer(input_path)
        self.calculate_evaluation_results(input_path, input_path.replace(".json", ".md"))