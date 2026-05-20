import utils
import configs.config_prompt as config_prompt


class Structurer():
    def __init__(self, model_path, num_to_generate=1):
        self.nlcomp2flcomp_system, self.nlcomp2flcomp_instruction = config_prompt.structure_prompt_nlcomp2flcomp()
        self.sampling_params = {
            "max_tokens": 2048,
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 20,
            "repetition_penalty": 1.05,
            "n": num_to_generate
        }
        self.local_model = utils.LocalModel(model_path, self.nlcomp2flcomp_system, self.sampling_params)
        
    def structure(self, input_path, output_path):
        data = utils.read_json(input_path)

        task_list = []
        for item in data:
            conditions = item.get("nl_conditions", [])
            conclusion = item.get("nl_conclusion", "")
            if conditions != ["No conditions"]:
                for cond in conditions:
                    input_data = self.nlcomp2flcomp_instruction.format(
                        text=cond, tag="condition"
                    )
                    messages = self.local_model.get_messages(input_data)
                    task_list.append(messages)
            input_data = self.nlcomp2flcomp_instruction.format(
                text=conclusion, tag="conclusion"
            )
            messages = self.local_model.get_messages(input_data)
            task_list.append(messages)
        responses = self.local_model.generate_batch(task_list)

        new_data = []
        curr_idx = 0    
        num_samples = len(responses[0]) if responses else 1

        for index, item in enumerate(data):
            conditions = item.get("nl_conditions", [])
            conclusion = item.get("nl_conclusion", "")
            if conditions == ["No conditions"]:
                batch_size_for_item = 1
                has_conditions = False
            else:
                batch_size_for_item = len(conditions) + 1
                has_conditions = True
            item_responses_block = responses[curr_idx : curr_idx + batch_size_for_item]
            curr_idx += batch_size_for_item

            for sub_idx in range(num_samples):
                new_item_index = f"{index + 1}_{sub_idx + 1}"
                
                new_item = {
                    "index": new_item_index,
                    "informal_statement": item.get("informal_statement", ""),
                    "nl_conditions": conditions,
                    "nl_conclusion": conclusion
                }

                if not has_conditions:
                    new_item["fl_conditions"] = ["No conditions"]
                    fl_conclusion_str = item_responses_block[0][sub_idx]
                else:
                    fl_conditions_list = []
                    for i in range(len(conditions)):
                        fl_conditions_list.append(item_responses_block[i][sub_idx])
                    new_item["fl_conditions"] = fl_conditions_list
                    fl_conclusion_str = item_responses_block[-1][sub_idx]

                new_item["fl_conclusion"] = fl_conclusion_str
                new_data.append(new_item)

        utils.write_json(output_path, new_data)