import os
import re
import json
import logging
from tqdm import tqdm
from openai import OpenAI
from vllm import LLM, SamplingParams
from transformers import AutoTokenizer
from kimina_client import KiminaClient
from concurrent.futures import ThreadPoolExecutor


CLIENT = KiminaClient(api_url="http://localhost:8000")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


def read_jsonl(file_path):
    data = []
    with open(file_path, "r") as f:
        for line in f:
            data.append(json.loads(line))
    return data

def read_json(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    return data


def write_json(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def data_infomal_stmt_key(benchmark):
    try:
        data = read_json(f"benchmark/{benchmark}.json")
    except:
        data = read_jsonl(f"benchmark/{benchmark}.jsonl")

    if data[0].get("natural_language"):
        informal_statement_key = "natural_language"
    elif data[0].get("informal_statement"):
        informal_statement_key = "informal_statement"
    elif data[0].get("theorem_statement"):
        informal_statement_key = "theorem_statement"
    return data, informal_statement_key


def extract_code(text_input):
    try:
        matches = re.findall(r'```(?:[lL]ean4?|[lL]ean)?\n(.*?)\n```', text_input, re.DOTALL)
        if matches:
            return matches[-1].strip()

        candidate = text_input.strip()
        marker = "No Lean code block found.\n"
        if candidate.startswith(marker):
            candidate = candidate[len(marker):].strip()

        looks_like_lean = bool(
            re.search(r'(^|\n)\s*(import\s+Mathlib|theorem\s+\w+|lemma\s+\w+|example\b)', candidate)
        )
        if looks_like_lean:
            return candidate

        return f"No Lean code block found.\n{text_input}"
    except Exception:
        return "Error during code extraction."
    

def extract_code_opt(text_input):
    try:
        pattern = r"###Lean4 code(.*?)###Operator tree"
        match = re.search(pattern, text_input, re.DOTALL)
        if match:
            extracted_code = match.group(1).strip()
            return extracted_code
        else:
            return "No Lean 4 code block found."
    except Exception:
        return "Error during code extraction."


def setup_logger(log_name, log_file_path):
    logger = logging.getLogger(log_name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    logger.propagate = False
    fh = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger


def lean4_scheduler(to_be_interaction_list, client=CLIENT):
    result_list = client.check(to_be_interaction_list, show_progress=False)
    return result_list.model_dump()


def check_compile_status(result):
    result = result["results"][0]
    try:
        message_list = result["response"]["messages"]
        all_errors = []

        for item in message_list:
            if item["severity"] == "error":
                new_item = {
                    "severity": item["severity"],
                    "position": {"column": item["pos"]["column"]},
                    "data": {"message": item["data"]}
                }
                all_errors.append(new_item)

        if len(all_errors) > 0:
            return False, all_errors[0], all_errors
        else:
            return True, None, []
    except:
        return True, None, []


class APIModel:
    def __init__(self, model_name, system_prompt):
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.api_key = ""
        self.base_url = ""
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
    def get_messages(self, input_data):
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": input_data},
        ]
   
    def generate(self, messages):
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
            response = completion.choices[0].message.content
            input_token = completion.usage.prompt_tokens
            output_token = completion.usage.completion_tokens
            return response, input_token, output_token
        except:
            return "[LLM ERROR]", 0, 0
        
    def generate_batch(self, task_list, desc="generate_batch", max_workers=10):
        responses = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.generate, task): task for task in task_list}
            for future in tqdm(futures, total=len(task_list), desc=desc):
                task = futures[future]
                response, input_token, output_token = future.result()
                responses.append((task, response, input_token, output_token))
        return responses


class LocalModel:
    def __init__(self, name_or_path, system_prompt, sampling_params):
        self.name_or_path = name_or_path
        self.system_prompt = system_prompt
        self.gpus = 4
        self.sampling_params = sampling_params
        self._init_model()

    def _init_model(self):
        self.model = LLM(
            model=self.name_or_path,
            tensor_parallel_size=self.gpus,
            trust_remote_code=True,
            dtype="bfloat16",
            gpu_memory_utilization=0.7,
        )
        self.tokenizer = AutoTokenizer.from_pretrained(self.name_or_path, trust_remote_code=True)
    
    def get_messages(self, input_data):
        messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": input_data}
            ]    
        return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    def generate_batch(self, task_list):
        responses = self.model.generate(task_list, sampling_params=SamplingParams(**self.sampling_params))
        parse_responses = [[o.text for o in response.outputs] for response in responses]
        return parse_responses