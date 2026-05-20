import re
import copy
import json
import random
import collections
import utils
import configs.config_prompt as config_prompt


class Splicer:
    def __init__(self):
        self.code_pattern = re.compile(r"###Lean4 code\s*(.*?)\s*(?:###Operator tree|$)", re.DOTALL)
        self.tree_pattern = re.compile(r"###Operator tree\s*(.*)", re.DOTALL)

    def _extract_components(self, text):
        linear_code = ""
        tree_json = None
        code_match = self.code_pattern.search(text)
        if code_match:
            linear_code = code_match.group(1).strip()
        else:
            if "###Operator tree" not in text:
                linear_code = text.strip()

        tree_match = self.tree_pattern.search(text)
        if tree_match:
            json_str = tree_match.group(1).strip()
            try:
                tree_json = json.loads(json_str)
            except json.JSONDecodeError:
                tree_json = None
        
        return linear_code, tree_json

    def _assemble_from_tree(self, node):
        if not isinstance(node, dict):
            return str(node)

        template = node.get("formal_content", "")
        children = node.get("children", [])

        if "<SLOT>" not in template:
            return template

        child_codes = [self._assemble_from_tree(child) for child in children]

        if template.count("<SLOT>") != len(child_codes):
            raise ValueError(f"Structure Mismatch: Template has {template.count('<SLOT>')} slots but found {len(child_codes)} children.")

        code = template
        for child_code in child_codes:
            code = code.replace("<SLOT>", child_code, 1)
        
        return code

    def _update_tree_variable(self, node, old_var, new_var):
        if not isinstance(node, dict):
            return
        if node.get("formal_content") == old_var:
            node["formal_content"] = new_var
        for child in node.get("children", []):
            self._update_tree_variable(child, old_var, new_var)

    def _process_single_condition(self, raw_text, var_counter, enable_rename=True):
        if raw_text == "No conditions":
            return None, raw_text, var_counter

        linear_code_fallback, tree_json = self._extract_components(raw_text)
        
        final_code = linear_code_fallback  
        final_raw_output = raw_text        
        
        is_generic_h = False
        if enable_rename and ":" in linear_code_fallback:
            parts = linear_code_fallback.split(":", 1)
            if parts[0].strip() == "(h":
                is_generic_h = True

        if tree_json:
            try:
                if is_generic_h:
                    pure_var_name = "h"
                    new_var_name = f"h{var_counter}"
                    var_counter += 1
                    self._update_tree_variable(tree_json, pure_var_name, new_var_name)

                assembled_code = self._assemble_from_tree(tree_json)
                final_code = assembled_code
                
                new_json_str = json.dumps(tree_json, ensure_ascii=False)
                final_raw_output = f"###Lean4 code\n{final_code}\n###Operator tree\n{new_json_str}"
                
            except Exception:
                final_code = linear_code_fallback
                final_raw_output = raw_text
        else:
            if is_generic_h:
                new_var_name = f"h{var_counter}"
                final_code = linear_code_fallback.replace("(h", f"({new_var_name}", 1)                
                final_raw_output = final_code 
                var_counter += 1

        return final_code, final_raw_output, var_counter

    def _construct_theorem(self, conditions_list, conclusion_raw):
        formatted_conds = []
        updated_raw_list = []
        var_counter = 1
        
        for raw_cond in conditions_list:
            code, updated_raw, new_counter = self._process_single_condition(raw_cond, var_counter, enable_rename=True)
            var_counter = new_counter
            if code:
                formatted_conds.append(code)
            updated_raw_list.append(updated_raw)

        concl_code, _, _ = self._process_single_condition(conclusion_raw, var_counter, enable_rename=False)
        
        if not concl_code: 
             concl_code, _ = self._extract_components(conclusion_raw)

        cond_str = " ".join(formatted_conds)
        if cond_str:
            theorem = f"theorem test {cond_str} : {concl_code} := by sorry"
        else:
            theorem = f"theorem test : {concl_code} := by sorry"
            
        return theorem, updated_raw_list

    def splice(self, input_path, output_path):
        data = utils.read_json(input_path)
        processed_data = []
        
        for item in data:
            new_entry = {
                "index": item.get("index"),
                "informal_statement": item.get("informal_statement")
            }
            
            nl_conds = item.get("nl_conditions", [])
            raw_conds = item.get("fl_conditions", [])

            if nl_conds == ["No conditions"]:
                raw_conds = []

            raw_concl = item.get("fl_conclusion", "")
            
            theorem_str, updated_conds = self._construct_theorem(raw_conds, raw_concl)
            
            new_entry["formal_statement"] = theorem_str
            new_entry["nl_conditions"] = nl_conds
            new_entry["fl_conditions"] = updated_conds 
            new_entry["nl_conclusion"] = item.get("nl_conclusion", "")
            new_entry["fl_conclusion"] = raw_concl 
            
            processed_data.append(new_entry)
            
        utils.write_json(output_path, processed_data)


class Repairer():
    def __init__(self, benchmark, model_name, only_global=False, max_repair_rounds=1, local_repair_turns=1, global_repair_turns=3):
        self.only_global = only_global
        self.max_repair_rounds = max_repair_rounds
        self.local_repair_turns = local_repair_turns
        self.global_repair_turns = global_repair_turns
        self.pattern = re.compile(r"###Lean4 code\s*(.*?)\s*(?:###Operator tree|$)", re.DOTALL)

        self.log_name = f"LeanRepair_{benchmark}_{model_name}_only_global" if self.only_global else "LeanRepair_{benchmark}_{model_name}"
        if self.only_global:
            self.log_path = f"experiment/{benchmark}/{model_name}/{model_name}_pass@1_g.log"   
        else:
            self.log_path = f"experiment/{benchmark}/{model_name}/{model_name}_pass@1_lg.log"     
        self.logger = utils.setup_logger(self.log_name, self.log_path)
        self.logger.info(f"Setting: Only Global = {self.only_global}, Max Repair Rounds = {self.max_repair_rounds}\n")
        self.logger.info(f"Local Repair Turns = {self.local_repair_turns}, Global Repair Turns = {self.global_repair_turns}\n")

        self.subcomp_system, self.subcomp_instruction = config_prompt.repair_prompt_subcomp()
        self.comp_system, self.comp_instruction = config_prompt.repair_prompt_comp()
        self.stmt_system, self.stmt_instruction = config_prompt.repair_prompt_stmt()

        self.subcomp_model = utils.APIModel("qwen3-max", self.subcomp_system)
        self.comp_model = utils.APIModel("qwen3-max", self.comp_system)
        self.stmt_model = utils.APIModel("qwen3-max", self.stmt_system)

    def find_error_component(self, formal_statement, error_message, fl_conditions, fl_conclusion):
        all_components = fl_conditions + [fl_conclusion]
        global_error_col = error_message.get("position", {}).get("column")
    
        current_search_start = 0
        for idx, comp_str in enumerate(all_components):
            parts = comp_str.split("###Operator tree")
            code_part = parts[0].replace("###Lean4 code", "").strip()
            if len(parts) > 1:
                tree_part_str = parts[1].strip()
            else:
                tree_part_str = None

            start_index = formal_statement.find(code_part, current_search_start)
            if start_index == -1:
                start_index = current_search_start 
            end_index = start_index + len(code_part)
            current_search_start = end_index
    
            if start_index <= global_error_col <= end_index:
                relative_col = global_error_col - start_index
                error_component_message = copy.deepcopy(error_message)
                error_component_message["position"]["column"] = relative_col
                component_id = idx+1
                if tree_part_str is None:
                    self.logger.warning(f"Component {code_part} has no operator tree. Fallback to component repair.\n")
                    return code_part, None, error_component_message, component_id

                try:
                    tree_part = json.loads(tree_part_str)
                    return code_part, tree_part, error_component_message, component_id
                except:
                    self.logger.error(f"Error in parsing operator tree JSON for component {code_part}.\n")
                    return code_part, None, error_component_message, component_id
        return None, None, None, None

    def _reconstruct_and_map(self, node, start_offset, parent=None, path=None):
        if path is None:
            path = []
        node["_parent"] = parent
        node["_start"] = start_offset
        node["_path"] = path
        formal_content = node.get("formal_content", "")
        children = node.get("children", [])
        parts = formal_content.split("<SLOT>")

        generated_text = ""
        current_offset = start_offset
        for i, part in enumerate(parts):
            generated_text += part
            current_offset += len(part)
            if i < len(children):
                child = children[i]
                child_text = self._reconstruct_and_map(child, current_offset, parent=node, path=path + [i])
                generated_text += child_text
                current_offset += len(child_text)
        node["_generated_text"] = generated_text
        node["_end"] = current_offset    
        return generated_text

    def _validate_tree_reconstruction(self, root, code_part, component_id, retry_counts):
        self._reconstruct_and_map(root, 0, parent=None)
        reconstructed_text = root.get("_generated_text", "").strip()
        original_text = code_part.strip()
        if reconstructed_text != original_text:
            self.logger.info(f"Tree reconstruction mismatch for component {component_id}. Fallback to whole component repair.\n")
            node_key = (component_id, 0, len(code_part))
            if retry_counts.get(node_key, 0) >= 1:
                return False, (None, None, None, None, True)
            should_reset = (retry_counts.get(node_key, 0) == 0)
            return False, (code_part, root, None, node_key, should_reset)
        return True, None

    def _find_initial_target_node(self, root, target_col):
        all_nodes = []
        def collect_nodes(n):
            if n.get("_generated_text", "").strip():
                all_nodes.append(n)
            for c in n.get("children", []):
                collect_nodes(c)
        collect_nodes(root)
        
        containing_nodes = [n for n in all_nodes if n["_start"] <= target_col <= n["_end"]]
        if containing_nodes:
            return min(containing_nodes, key=lambda n: n["_end"] - n["_start"])
        else:
            if all_nodes:
                def dist(n, c):
                    s, e = n["_start"], n["_end"]
                    if s <= c <= e: return 0
                    return min(abs(c - s), abs(c - e))
                return min(all_nodes, key=lambda n: dist(n, target_col))
            else:
                return root

    def _is_redundant_wrapper(self, parent_node, child_node, child_code):
        parent_code = parent_node.get("_generated_text", "").strip()
        child_code = child_code.strip()
        if len(parent_code) <= len(child_code):
            return False
    
        if (parent_code.startswith("(") and parent_code.endswith(")")) or \
           (parent_code.startswith("[") and parent_code.endswith("]")) or \
           (parent_code.startswith("{") and parent_code.endswith("}")):
            inner_content = parent_code[1:-1].strip()
            if inner_content == child_code:
                return True

        match_label = re.match(r"^\(\s*h\d+\s*:\s*(.*)\s*\)$", parent_code, re.DOTALL)
        if match_label:
            content_after_label = match_label.group(1).strip()
            if content_after_label == child_code:
                return True
        return False

    def _backtrack_logic(self, start_node, component_id, retry_counts):
        selected_node = start_node
        
        while selected_node:
            selected_key = (component_id, selected_node.get("_start", 0), selected_node.get("_end", 0))
            current_count = retry_counts.get(selected_key, 0)
            is_exhausted = current_count >= 1
            
            if not is_exhausted:
                return selected_node, selected_key, False
            
            parent_node = selected_node.get("_parent")
            if parent_node is None:
                return None, None, True
        
            selected_code = selected_node.get("_generated_text", "").strip()
            if selected_code and self._is_redundant_wrapper(parent_node, selected_node, selected_code):
                self.logger.info(f"Skipping redundant parent: '{parent_node.get('_generated_text', '').strip()}' for child: '{selected_code}'\n")                
                grandparent_node = parent_node.get("_parent")
                if grandparent_node is None:
                    return None, None, True
                selected_node = grandparent_node
                continue
            else:
                selected_node = parent_node
                
        return None, None, True

    def _clean_subtree(self, node):
        clean_node = {}
        for key, value in node.items():
            if key.startswith("_"):
                continue
            if key == "children" and isinstance(value, list):
                clean_node["children"] = [self._clean_subtree(child) for child in value]
            else:
                clean_node[key] = value
        return clean_node
    
    def _construct_result(self, selected_node, selected_key, target_col, error_component_message):
        subcode_code = selected_node.get("_generated_text", "")        
        scope_start = selected_node.get("_start", 0)
        subtree_part = self._clean_subtree(selected_node)
        
        relative_pos = target_col - scope_start
        error_subcomponent_message = copy.deepcopy(error_component_message)
        error_subcomponent_message["position"]["column"] = relative_pos
        selected_path = selected_node.get("_path", []) 
        return subcode_code, subtree_part, error_subcomponent_message, selected_key, selected_path

    def find_error_subcomponent(self, code_part, tree_part, error_component_message, component_id, retry_counts):
        if tree_part is None:
             self.logger.error("Unexpected None tree_part in find_error_subcomponent\n")
             return None, None, None, None, [], True

        root = copy.deepcopy(tree_part)
        is_valid, fallback_result = self._validate_tree_reconstruction(root, code_part, component_id, retry_counts)
        if not is_valid:
            if fallback_result[4] is True: 
                 return fallback_result[0], fallback_result[1], error_component_message, fallback_result[3], [], fallback_result[4]
            f_code, f_tree, _, f_key, f_reset = fallback_result
            return f_code, f_tree, error_component_message, f_key, [], f_reset

        target_col = error_component_message.get("position", {}).get("column")
        raw_target_node = self._find_initial_target_node(root, target_col)
        initial_scope_node = raw_target_node.get("_parent") if raw_target_node.get("_parent") else raw_target_node
        target_key = (component_id, initial_scope_node.get("_start", 0), initial_scope_node.get("_end", 0))
        selected_node, selected_key, is_abort = self._backtrack_logic(initial_scope_node, component_id, retry_counts)
        
        if is_abort:
            self.logger.info("All nodes exhausted for subcomponent repair.\n")
            return None, None, None, None, [], True 

        current_count = retry_counts.get(selected_key, 0)
        should_reset = (selected_key != target_key) and (current_count == 0)
        subcode, subtree, sub_msg, final_key, node_path = self._construct_result(selected_node, selected_key, target_col, error_component_message)
        return subcode, subtree, sub_msg, final_key, node_path, should_reset

    def _find_previous_variables(self, formal_statement, fl_conditions, error_component_start_index):
        variables = []
        current_search_start = 0
        hypothesis_pattern = re.compile(r"^\(h\d+\s*:")

        for comp_str in fl_conditions:
            parts = comp_str.split("###Operator tree")
            code_part = parts[0].replace("###Lean4 code", "").strip()
            start_index = formal_statement.find(code_part, current_search_start)
            end_index = start_index + len(code_part)
            current_search_start = end_index

            end_index = start_index + len(code_part)
            if start_index <= error_component_start_index < end_index:
                break 
            if start_index >= error_component_start_index:
                break
            if not hypothesis_pattern.match(code_part):
                variables.append(code_part)
        return variables

    def _locate_error_context(self, item, error_message, node_retry_counts):
        self.logger.info(f"**[Locate]** Locating error component.\n")
        comp_code, comp_tree, comp_msg, comp_id = self.find_error_component(item["formal_statement"], error_message, item["fl_conditions"], item["fl_conclusion"])
        sub_code, sub_tree, sub_msg, node_key, node_path = None, None, None, None, []
        should_reset = False

        if comp_code is not None:
            self.logger.info(f"Error component code: {comp_code}\n")
            self.logger.info(f"Error component tree: {json.dumps(comp_tree, ensure_ascii=False)}\n")
            self.logger.info(f"Error component message: {json.dumps(comp_msg)}\n")
            self.logger.info(f"Error component ID: {comp_id}\n")

            self.logger.info(f"**[Locate]** Locating error subcomponent.\n")
            sub_code, sub_tree, sub_msg, node_key, node_path, should_reset = self.find_error_subcomponent(comp_code, comp_tree, comp_msg, comp_id, node_retry_counts)
            if sub_code is not None:
                self.logger.info(f"Error subcomponent code: {sub_code}\n")
                log_tree = self._clean_subtree(sub_tree) if sub_tree else None
                self.logger.info(f"Error subcomponent tree: {json.dumps(log_tree, ensure_ascii=False)}\n")
                self.logger.info(f"Error subcomponent message: {json.dumps(sub_msg)}\n")
                self.logger.info(f"Error subcomponent node key: {node_key}\n")
            else:
                self.logger.info("Component switched to statement level repair.\n")

        return {
            "component_code": comp_code,
            "component_tree": comp_tree,
            "component_msg": comp_msg,
            "component_id": comp_id,
            "subcomponent_code": sub_code,
            "subcomponent_tree": sub_tree,
            "subcomponent_msg": sub_msg,
            "node_key": node_key,
            "node_path": node_path,
            "should_reset": should_reset
        }

    def _get_informal_component_text(self, item, component_id):
        try:
            conds = item.get("nl_conditions", [])
            if conds == ["No conditions"]:
                conds = []
            idx = component_id - 1
            if idx < len(conds):
                return conds[idx]
            elif idx == len(conds):
                return item.get("nl_conclusion", "")
            else:
                return ""
        except:
            return ""

    def _update_component_tree(self, component_tree, target_path, repaired_subcomponent_code):
        if not target_path:
            return {
                "formal_content": repaired_subcomponent_code,
                "children": []
            }

        target_idx = target_path[0]
        remaining_path = target_path[1:]
        current_children = component_tree.get("children", [])
        new_children = []

        for i, child in enumerate(current_children):
            if i == target_idx:
                updated_child = self._update_component_tree(child, remaining_path, repaired_subcomponent_code)
                new_children.append(updated_child)
            else:
                new_children.append(child)
        return {
            "formal_content": component_tree.get("formal_content", ""),
            "children": new_children
        }
    
    def _apply_subcomponent_update(self, item, ctx, repaired_sub_code, repaired_comp_code, candidate_stmt):
        repaired_tree = self._update_component_tree(ctx["component_tree"], ctx["node_path"], repaired_sub_code)
        self.logger.info(f"Updated component code: {repaired_comp_code}\n")
        self.logger.info(f"Updated component tree: {json.dumps(repaired_tree, ensure_ascii=False)}\n")

        new_conditions = []
        target_code = ctx["component_code"].strip()
        for comp in item.get("fl_conditions", []):
            match = self.pattern.search(comp)
            current_code = match.group(1).strip() if match else ""            
            if current_code == target_code:
                new_entry = f"###Lean4 code\n{repaired_comp_code}\n###Operator tree\n{json.dumps(repaired_tree, ensure_ascii=False)}"
                new_conditions.append(new_entry)
            else:
                new_conditions.append(comp)
        item["fl_conditions"] = new_conditions

        concl_match = self.pattern.search(item["fl_conclusion"])
        concl_code = concl_match.group(1).strip() if concl_match else ""
        if concl_code == target_code:
            item["fl_conclusion"] = f"###Lean4 code\n{repaired_comp_code}\n###Operator tree\n{json.dumps(repaired_tree, ensure_ascii=False)}"
        item["formal_statement"] = candidate_stmt
        self.logger.info(f"Updated formal statement: {item['formal_statement']}\n")

    def _strategy_local_repair(self, item, ctx, node_retry_counts, output_path, full_data):
        comp_code = ctx["component_code"]
        sub_code = ctx["subcomponent_code"]
        is_subcomponent_level = (sub_code != comp_code)
        if is_subcomponent_level:
            repair_level = "subcomponent"
            self.logger.info(f"**[Repair]** Repairing by LLM (Local Strategy - {repair_level}).\n")
            current_model = self.subcomp_model
            current_instruction = self.subcomp_instruction
        else:
            repair_level = "component"
            self.logger.info(f"**[Repair]** Repairing by LLM (Local Strategy - {repair_level}).\n")
            current_model = self.comp_model
            current_instruction = self.comp_instruction

        self.logger.info(f"Broken code: {sub_code}\n")
        original_sub_start_idx = item["formal_statement"].find(sub_code)
        prev_vars = self._find_previous_variables(item["formal_statement"], item.get("fl_conditions", []), original_sub_start_idx)
        self.logger.info(f"Previously declared variables: {prev_vars}\n")
        self.logger.info(f"Error message: {json.dumps(ctx['subcomponent_msg'])}\n")

        prompt_args = {
            "broken_code": sub_code,
            "error_message": json.dumps(ctx["subcomponent_msg"]),
            "previously_declared_variables": prev_vars,
        }
        informal_comp_text = self._get_informal_component_text(item, ctx["component_id"])
        self.logger.info(f"Informal component text: {informal_comp_text}\n") if repair_level == "component" else None
        prompt_args["informal_component"] = informal_comp_text

        initial_instruction = current_instruction.format(**prompt_args)
        messages = current_model.get_messages(initial_instruction)
        last_trial_result = None
        total_input_tokens = 0
        total_output_tokens = 0

        for turn in range(self.local_repair_turns):
            self.logger.info(f"--- Local Repair ({repair_level}) Turn {turn + 1}/{self.local_repair_turns} ---\n")
            llm_output, input_token, output_token = current_model.generate(messages)
            total_input_tokens += input_token
            total_output_tokens += output_token
            self.logger.info(f"LLM Output: {llm_output}\n")

            marker = "**Corrected Code Snippet:**"
            parts = llm_output.split(marker)
            if len(parts) > 1:
                raw_code = parts[-1]
                cleaned_code = raw_code.replace("```lean", "").replace("```", "").replace(":= by sorry", "")
                cleaned_code = re.sub(r"--.*(?:\n|$)", "", cleaned_code)
                repaired_sub_code = cleaned_code.strip()
            else:
                repaired_sub_code = sub_code

            self.logger.info(f"**[Construct]** Constructing candidate items.\n")
            repaired_comp_code = comp_code.replace(sub_code, repaired_sub_code, 1)
            candidate_stmt = item["formal_statement"].replace(comp_code, repaired_comp_code, 1)
            self.logger.info(f"Candidate subcomponent code: {repaired_sub_code}\n")
            self.logger.info(f"Candidate formal statement: {candidate_stmt}\n")

            self.logger.info(f"**[Compile]** Verifying candidate code (Turn {turn + 1}).\n")
            trial_result = utils.lean4_scheduler(["import Mathlib\n" + candidate_stmt])
            trial_is_success, trial_error_message, trial_all_error_messages = utils.check_compile_status(trial_result)
            last_trial_result = (trial_is_success, trial_error_message, trial_all_error_messages)

            is_partial = False
            if not trial_is_success:
                trial_col = trial_error_message.get("position", {}).get("column", -1)
                new_sub_end = original_sub_start_idx + len(repaired_sub_code)
                if trial_col != -1 and (trial_col < original_sub_start_idx or trial_col > new_sub_end):
                    is_partial = True

            if trial_is_success or is_partial:
                status_msg = "COMPLETE SUCCESS" if trial_is_success else "PARTIAL SUCCESS"
                self.logger.info(f"**[Update]** {status_msg} at Turn {turn + 1}. Update the corresponding component and formal statement.\n")
                node_retry_counts.clear()
                self._apply_subcomponent_update(item, ctx, repaired_sub_code, repaired_comp_code, candidate_stmt)
                if trial_is_success:
                    item["Compile"] = "True"
                    utils.write_json(output_path, full_data)
                    return {"status": "complete_success", "usage": (total_input_tokens, total_output_tokens)}
                else:
                    utils.write_json(output_path, full_data)
                    return {
                        "status": "partial_success", 
                        "trial_error_message": trial_error_message, 
                        "trial_all_error_messages": trial_all_error_messages,
                        "usage": (total_input_tokens, total_output_tokens)
                    }
            
            if turn < self.local_repair_turns - 1:
                self.logger.info(f"Turn {turn + 1} failed. Appending error message to history for next turn.\n")
                messages.append({"role": "assistant", "content": llm_output})
                error_feedback = f"The code snippet you provided caused the following compile error:\n{json.dumps(trial_error_message)}\nPlease fix the code snippet based on this error."
                messages.append({"role": "user", "content": error_feedback})
            else:
                self.logger.info("Max turns reached without success for local repair.\n")

        trial_is_success, trial_error_message, trial_all_error_messages = last_trial_result
        self.logger.info(f"**[Update]** Local repair ({repair_level}) FAILED after {self.local_repair_turns} turns. Discarding updates.\n")
        if ctx["node_key"]:
            node_retry_counts[ctx["node_key"]] += 1
            self.logger.info(f"Incremented retry count for node {ctx['node_key']} to {node_retry_counts[ctx['node_key']]}.\n")
            if "position" in trial_error_message:
                del trial_error_message["position"]
        return {
            "status": "failed", 
            "previous_failed_attempt": repaired_sub_code, 
            "trial_error_message": trial_error_message, 
            "trial_all_error_messages": trial_all_error_messages,
            "usage": (total_input_tokens, total_output_tokens)
        }
        
    def _strategy_global_repair(self, item, all_error_messages, output_path, full_data):
        self.logger.info(f"**[Repair]** Repairing by LLM (Global Strategy - Statement).\n")
        self.logger.info(f"Broken code: {item['formal_statement']}\n")
        self.logger.info(f"Error messages: {json.dumps(all_error_messages)}\n")

        prompt_args = {
            "broken_statement": item["formal_statement"],
            "error_message": json.dumps(all_error_messages),
        }
        informal_stmt = item.get("informal_statement", "")
        self.logger.info(f"Informal statement: {informal_stmt}\n")
        prompt_args["informal_statement"] = informal_stmt

        initial_instruction = self.stmt_instruction.format(**prompt_args)
        messages = self.stmt_model.get_messages(initial_instruction)
        last_trial_result = None
        candidate_formal_statement = item["formal_statement"]
        
        total_input_tokens = 0
        total_output_tokens = 0

        for turn in range(self.global_repair_turns):
            self.logger.info(f"--- Global Repair Turn {turn + 1}/{self.global_repair_turns} ---\n")
            llm_output, input_token, output_token = self.stmt_model.generate(messages)
            total_input_tokens += input_token
            total_output_tokens += output_token
            self.logger.info(f"LLM Output: {llm_output}\n")

            marker = "**Corrected Formal Statement:**"
            parts = llm_output.split(marker)
            if len(parts) > 1:
                raw_code = parts[-1]
                cleaned_code = raw_code.replace("```lean", "").replace("```", "")
                cleaned_code = re.sub(r"--.*(?:\n|$)", "", cleaned_code)
                candidate_formal_statement = cleaned_code.strip()
            else:
                pass
            self.logger.info(f"Candidate formal statement: {candidate_formal_statement}\n")

            self.logger.info(f"**[Compile]** Verifying global candidate code.\n")
            trial_compile_result = utils.lean4_scheduler(["import Mathlib\n" + candidate_formal_statement])
            trial_is_success, trial_error_message, trial_all_error_messages = utils.check_compile_status(trial_compile_result)                
            last_trial_result = (trial_is_success, trial_error_message, trial_all_error_messages)

            if trial_is_success:
                self.logger.info(f"**[Update]** Global repair COMPLETE SUCCESS at Turn {turn + 1}.\n")
                item["formal_statement"] = candidate_formal_statement
                item["Compile"] = "True"
                utils.write_json(output_path, full_data)
                return {"status": "complete_success", "usage": (total_input_tokens, total_output_tokens)}
            
            if turn < self.global_repair_turns - 1:
                self.logger.info(f"Turn {turn + 1} failed. Appending error message to history for next turn.\n")
                messages.append({"role": "assistant", "content": llm_output})
                error_feedback = f"The code you provided caused the following compile error:\n{json.dumps(trial_all_error_messages)}\nPlease fix the code based on this error."
                messages.append({"role": "user", "content": error_feedback})
            else:
                self.logger.info("Max turns reached without complete success.\n")

        trial_is_success, trial_error_message, trial_all_error_messages = last_trial_result
        current_err_len = len(trial_all_error_messages)
        origin_err_len = len(all_error_messages)
        is_reduced = current_err_len < origin_err_len
        is_lucky_equal = (current_err_len == origin_err_len) and (random.random() < 0.5)

        if is_reduced or is_lucky_equal:
            reason = "Errors reduced" if is_reduced else "Errors unchanged but accepted by chance"
            self.logger.info(f"**[Update]** Global repair PARTIAL SUCCESS ({reason}). Updating formal statement.\n")
            item["formal_statement"] = candidate_formal_statement
            utils.write_json(output_path, full_data)                 
            return {
                "status": "partial_success", 
                "trial_error_message": trial_error_message, 
                "trial_all_error_messages": trial_all_error_messages,
                "usage": (total_input_tokens, total_output_tokens)
            }
        else:
            self.logger.info(f"**[Update]** Global repair FAILED. Retrying next round if available...\n")
            return {
                "status": "failed", 
                "previous_failed_attempt": candidate_formal_statement, 
                "trial_error_message": trial_error_message, 
                "trial_all_error_messages": trial_all_error_messages,
                "usage": (total_input_tokens, total_output_tokens)
            }

    def _process_single_item(self, index, item, output_path, full_data):
        compile_result = utils.lean4_scheduler(["import Mathlib\n" + item["formal_statement"]])
        is_success, error_message, all_error_messages = utils.check_compile_status(compile_result)
        if is_success:
            self.logger.info(f"**[Status]** Item {index} originally compiled successfully. No repair needed.\n")
            item["Compile"] = "Originally True"
            utils.write_json(output_path, full_data)
            return

        for round_idx in range(self.max_repair_rounds):
            self.logger.info(f"========== Round {round_idx + 1} / {self.max_repair_rounds} ==========\n")
            node_retry_counts = collections.defaultdict(int)
            is_global_mode = self.only_global
            
            while True:
                if round_idx > 0 or node_retry_counts:
                    compile_result = utils.lean4_scheduler(["import Mathlib\n" + item["formal_statement"]])
                    is_success, error_message, all_error_messages = utils.check_compile_status(compile_result)
                    if is_success:
                        self.logger.info(f"**[Success]** Item {index} compiled successfully at Round {round_idx + 1}.\n")
                        item["Compile"] = "True"
                        utils.write_json(output_path, full_data)
                        return

                ctx = None
                if not is_global_mode:
                    ctx = self._locate_error_context(item, error_message, node_retry_counts)            
                    if ctx["subcomponent_code"] is None:
                        self.logger.info(f"Switching to global repair strategy (Reached Statement Level).\n")
                        is_global_mode = True

                if is_global_mode:
                    result = self._strategy_global_repair(item, all_error_messages, output_path, full_data)
                    if result["status"] == "complete_success":
                        self.logger.info(f"Global repair COMPLETE SUCCESS.\n")
                        return
                    self.logger.info(f"Global repair finished (Status: {result['status']}). End of Round {round_idx + 1}.\n")
                    break 
                else:
                    result = self._strategy_local_repair(item, ctx, node_retry_counts, output_path, full_data)
                    
                    if result["status"] == "complete_success":
                        self.logger.info(f"**[Flow]** Local repair COMPLETE SUCCESS. Switching to Global Repair (Mandatory).\n")
                        is_global_mode = True
                        error_message = {}
                        all_error_messages = []
                    elif result["status"] == "partial_success":
                        error_message = result.get("trial_error_message", {})
                        all_error_messages = result.get("trial_all_error_messages", {})
                    else:
                        pass

        if item.get("Compile") != "True":
            item["Compile"] = "False"
            self.logger.info(f"**[Status]** Item {index} could not be fully repaired after {self.max_repair_rounds} rounds.\n")
            utils.write_json(output_path, full_data)

    def repair(self, input_path):
        try:
            if self.only_global:
                data = utils.read_json(input_path.replace(".json", f"_g.json"))
            else:
                data = utils.read_json(input_path.replace(".json", f"_lg.json"))
            self.logger.info("Resuming from existing file.\n")
        except:
            data = utils.read_json(input_path)
            self.logger.info("Starting fresh repair process.\n")

        if self.only_global:
            output_path = input_path.replace(".json", f"_g.json")
        else:
            output_path = input_path.replace(".json", f"_lg.json")

        for item in data:
            index = item["index"].split("_")[0]
            self.logger.info(f"==================== Processing item {index} ====================\n")
            if item.get("Compile") is not None:
                self.logger.info(f"Item {index} already processed. Skipping.\n")
            else:
                self._process_single_item(index, item, output_path, data)
            self.logger.info(f"==================== Finished processing item {index} ====================\n\n\n")