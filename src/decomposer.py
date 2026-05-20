import re
import utils
import configs.config_prompt as config_prompt


class Decomposer:
    def __init__(self):
        self.nl2nlcomp_system, self.nl2nlcomp_instruction = config_prompt.decompose_prompt_nl2nlcomp()
        self.nl2nlcomp_model = utils.APIModel("qwen3-max", self.nl2nlcomp_system)

    def parse_conditions_and_conclusion(self, llm_output):
        parts = llm_output.split("**Conclusion:**")
        if len(parts) != 2:
            return ["[LLM ERROR]"]

        conditions_part, conclusion_part = parts
        
        condition_blocks = re.findall(
            r'^\d+\.\s+(.*?)(?=^\d+\.|\Z)',
            conditions_part,
            re.MULTILINE | re.DOTALL
        )
        conditions = [block.strip() for block in condition_blocks]
        if not conditions:
            conditions = ["No conditions"]
        match = re.search(r'-\s*(.*)', conclusion_part, re.DOTALL)
        if not match:
            return ["[PARSE ERROR]"]

        conclusion = match.group(1).strip()

        return [conditions, conclusion]

    def decompose(self, benchmark, output_path):
        data, informal_statement_key = utils.data_infomal_stmt_key(benchmark)

        task_list = []
        for item in data:
            informal_statement = item[informal_statement_key]
            input_data = self.nl2nlcomp_instruction.format(
                problem_statement=informal_statement
            )
            messages = self.nl2nlcomp_model.get_messages(input_data)
            task_list.append(messages)
        llm_outputs = self.nl2nlcomp_model.generate_batch(task_list, desc="NLComp Decomposition", max_workers=10)

        new_data = []
        for index, (task, decomposed_output, _, _) in enumerate(llm_outputs):
            parse_output = self.parse_conditions_and_conclusion(decomposed_output)
            if parse_output == ["[LLM ERROR]"] or parse_output == ["[PARSE ERROR]"]:
                new_data.append({
                    "index": index + 1,
                    "informal_statement": data[index][informal_statement_key],
                    "llm_output": decomposed_output,
                    "nl_conditions": ["[DECOMPOSITION ERROR]"],
                    "nl_conclusion": "[DECOMPOSITION ERROR]",
                })
            else:
                conditions, conclusion = parse_output
                new_data.append({
                    "index": index + 1,
                    "informal_statement": data[index][informal_statement_key],
                    "llm_output": decomposed_output,
                    "nl_conditions": conditions,
                    "nl_conclusion": conclusion,
                })
        utils.write_json(output_path, new_data)