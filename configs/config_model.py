BASELINE_MODEL_ROOT = "../LLaMA-Factory/Models/LLM"
_MODEL_CONFIGS_RAW = {
	"qwen": {
		"type": "e2e_api",
		"path": "qwen3-max",
		"system": "You are an expert in mathematics and Lean 4.",
		"instruction": "Please autoformalize the following problem in Lean 4 with a header. Use the following theorem names: my_favorite_theorem.\n{informal_statement}\n\nYour code should start with \n```Lean4\nimport Mathlib\n```\n\nYou should only output the theorem statement in Lean 4 format, ending with `by sorry`. You should NOT output the proof.\n",
		"sampling_params": {},
		"gen_kwargs": {"desc": "Qwen Autoformalization", "max_workers": 10},
		"post_process": "extract_code",
	},
	"codex": {
		"type": "e2e_api",
		"path": "gpt-5.3-codex",
		"system": "You are an expert in mathematics and Lean 4.",
		"instruction": "Please autoformalize the following problem in Lean 4 with a header. Use the following theorem names: my_favorite_theorem.\n{informal_statement}\n\nYour code should start with \n```Lean4\nimport Mathlib\n```\n\nYou should only output the theorem statement in Lean 4 format, ending with `by sorry`. You should NOT output the proof.\n",
		"sampling_params": {},
		"gen_kwargs": {"desc": "Codex Autoformalization", "max_workers": 10},
		"post_process": "extract_code",
	},
	"opus": {
		"type": "e2e_api",
		"path": "claude-opus-4-6",
		"system": "You are an expert in mathematics and Lean 4.",
		"instruction": "Please autoformalize the following problem in Lean 4 with a header. Use the following theorem names: my_favorite_theorem.\n{informal_statement}\n\nYour code should start with \n```Lean4\nimport Mathlib\n```\n\nYou should only output the theorem statement in Lean 4 format, ending with `by sorry`. You should NOT output the proof.\n",
		"sampling_params": {},
		"gen_kwargs": {"desc": "Opus Autoformalization", "max_workers": 10},
		"post_process": "extract_code",
	},
	"kimina": {
		"type": "e2e",
		"path": f"{BASELINE_MODEL_ROOT}/Kimina-Autoformalizer-7B",
		"system": "You are an expert in mathematics and Lean 4.",
		"instruction": "Please autoformalize the following problem in Lean 4 with a header. Use the following theorem names: my_favorite_theorem.\n\n{informal_statement}",
		"sampling_params": {"temperature": 0.6, "top_p": 0.95, "max_tokens": 2048},
		"post_process": None,
	},
	"stepfun_7b": {
		"type": "e2e",
		"path": f"{BASELINE_MODEL_ROOT}/StepFun-Formalizer-7B",
		"system": "You are an expert in mathematics and Lean 4.",
		"instruction": "Please autoformalize the following problem in Lean 4 with a header. Use the following theorem names: my_favorite_theorem.\n\n{informal_statement}\n\nYour code should start with:\n```Lean4\n{header}\n```\n",
		"sampling_params": {"temperature": 0.6, "top_p": 0.95, "max_tokens": 16384},
		"template_args": {"header": "import Mathlib\n"},
		"append_think": True,
		"post_process": "extract_code",
	},
	"stepfun_32b": {
		"type": "e2e",
		"path": f"{BASELINE_MODEL_ROOT}/StepFun-Formalizer-32B",
		"system": "You are an expert in mathematics and Lean 4.",
		"instruction": "Please autoformalize the following problem in Lean 4 with a header. Use the following theorem names: my_favorite_theorem.\n\n{informal_statement}\n\nYour code should start with:\n```Lean4\n{header}\n```\n",
		"sampling_params": {"temperature": 0.6, "top_p": 0.95, "max_tokens": 16384},
		"template_args": {"header": "import Mathlib\n"},
		"append_think": True,
		"post_process": "extract_code",
	},
	"goedel_8b": {
		"type": "e2e",
		"path": f"{BASELINE_MODEL_ROOT}/Goedel-Formalizer-V2-8B",
		"system": "",
		"instruction": (
			"Please autoformalize the following natural language problem statement in Lean 4. "
			"Use the following theorem name: {problem_name}\n"
			"The natural language statement is: \n"
			"{informal_statement_content}"
			"Think before you provide the lean statement."
		),
		"sampling_params": {"temperature": 0.9, "max_tokens": 16384, "top_p": 0.95, "top_k": 20},
		"template_args": {"problem_name": "test_problem"},
		"input_key_map": "informal_statement_content",
		"post_process": "extract_code",
	},
	"goedel_32b": {
		"type": "e2e",
		"path": f"{BASELINE_MODEL_ROOT}/Goedel-Formalizer-V2-32B",
		"system": "",
		"instruction": (
			"Please autoformalize the following natural language problem statement in Lean 4. "
			"Use the following theorem name: {problem_name}\n"
			"The natural language statement is: \n"
			"{informal_statement_content}"
			"Think before you provide the lean statement."
		),
		"sampling_params": {"temperature": 0.9, "max_tokens": 16384, "top_p": 0.95, "top_k": 20},
		"template_args": {"problem_name": "test_problem"},
		"input_key_map": "informal_statement_content",
		"post_process": "extract_code",
	},
	"atf_8b": {
		"type": "e2e",
		"path": f"{BASELINE_MODEL_ROOT}/ATF-8B",
		"system": """
You are an expert in mathematics and Lean 4. Your task is to convert natural language problems into valid Lean 4 formal statements (Compatible with Lean 4 v4.9).

Your code must begin with:

import Mathlib
import Aesop


You MUST use the provided tools to verify your Lean 4 statements:

- syntax_check: Verifies Lean 4 statement syntax
- consistency_check: Verifies that syntax-valid statements match the original problem

Verification workflow:

- Analyze the problem and create initial Lean 4 statement
- Call syntax_check to verify compilation
- If syntax check passes, call consistency_check
- If any check fails, analyze errors, modify code and restart verification
- Repeat until BOTH checks pass
""".strip(),
		"instruction": "Please autoformalize the following problem in Lean 4 with a header. Use the following theorem names: my_favorite_theorem.\n\n{informal_statement}",
		"sampling_params": {"temperature": 0.6, "max_tokens": 32768},
		"post_process": "extract_code",
	},
	"atf_32b": {
		"type": "e2e",
		"path": f"{BASELINE_MODEL_ROOT}/ATF-32B",
		"system": """
You are an expert in mathematics and Lean 4. Your task is to convert natural language problems into valid Lean 4 formal statements (Compatible with Lean 4 v4.9).

Your code must begin with:

import Mathlib
import Aesop


You MUST use the provided tools to verify your Lean 4 statements:

- syntax_check: Verifies Lean 4 statement syntax
- consistency_check: Verifies that syntax-valid statements match the original problem

Verification workflow:

- Analyze the problem and create initial Lean 4 statement
- Call syntax_check to verify compilation
- If syntax check passes, call consistency_check
- If any check fails, analyze errors, modify code and restart verification
- Repeat until BOTH checks pass
""".strip(),
		"instruction": "Please autoformalize the following problem in Lean 4 with a header. Use the following theorem names: my_favorite_theorem.\n\n{informal_statement}",
		"sampling_params": {"temperature": 0.6, "max_tokens": 32768},
		"post_process": "extract_code",
	},
	"nlstmt2flstmt": {
		"type": "e2e",
		"path": f"{BASELINE_MODEL_ROOT}/nlstmt2flstmt",
		"system": "",
		"instruction": "Please translate the natural language statement into Lean4 code.\n{informal_statement}",
		"sampling_params": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "max_tokens": 4096, "repetition_penalty": 1.05},
		"post_process": None,
	},
	"nlstmt2flstmt(opt)": {
		"type": "e2e",
		"path": f"{BASELINE_MODEL_ROOT}/nlstmt2flstmt(opt)",
		"system": "",
		"instruction": "Please translate the natural language statement into Lean4 code, and then parse it into a structured operator tree in JSON format. Use 'formal_content' for the operator logic (with '<SLOT>' as placeholders) and 'children' for the nested arguments.\n{informal_statement}",
		"sampling_params": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "max_tokens": 4096, "repetition_penalty": 1.05},
		"post_process": "extract_code_opt",
	},
	"nlstmt2flstmt(cl)": {
		"type": "e2e",
		"path": f"{BASELINE_MODEL_ROOT}/nlstmt2flstmt(cl)",
		"system": "",
		"instruction": "Please translate the natural language statement into Lean4 code, and then parse it into a structured operator tree in JSON format. Use 'formal_content' for the operator logic (with '<SLOT>' as placeholders) and 'children' for the nested arguments.\n{informal_statement}",
		"sampling_params": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "max_tokens": 4096, "repetition_penalty": 1.05},
		"post_process": "extract_code_opt",
	},
	"nlcomp2flcomp": {
		"type": "non_e2e",
		"path": f"{BASELINE_MODEL_ROOT}/nlcomp2flcomp",
		"system": "",
		"instruction": "Please translate the natural language component into Lean4 code.\nComponent: {text}\nTag: {tag}",
		"sampling_params": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "max_tokens": 2048, "repetition_penalty": 1.05},
		"post_process": None,
	},
	"nlcomp2flcomp(opt)": {
		"type": "non_e2e",
		"path": f"{BASELINE_MODEL_ROOT}/nlcomp2flcomp(opt)",
		"system": "",
		"instruction": "Please translate the natural language component into Lean4 code, and then parse it into a structured operator tree in JSON format. Use 'formal_content' for the operator logic (with '<SLOT>' as placeholders) and 'children' for the nested arguments.\nComponent: {text}\nTag: {tag}",
		"sampling_params": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "max_tokens": 2048, "repetition_penalty": 1.05},
		"post_process": None,
	},
	"nlcomp2flcomp(cl)": {
		"type": "non_e2e",
		"path": f"{BASELINE_MODEL_ROOT}/nlcomp2flcomp(cl)",
		"system": "",
		"instruction": "Please translate the natural language component into Lean4 code, and then parse it into a structured operator tree in JSON format. Use 'formal_content' for the operator logic (with '<SLOT>' as placeholders) and 'children' for the nested arguments.\nComponent: {text}\nTag: {tag}",
		"sampling_params": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "max_tokens": 2048, "repetition_penalty": 1.05},
		"post_process": None,
	},
}


def get_model_config_raw(model_name, n=1):
	cfg = _MODEL_CONFIGS_RAW[model_name].copy()
	if "sampling_params" in cfg:
		cfg["sampling_params"] = cfg["sampling_params"].copy()
		cfg["sampling_params"]["n"] = n
	return cfg


def get_model_config(model_name, n=1, post_process_map=None):
	cfg = get_model_config_raw(model_name, n=n)
	if post_process_map is None:
		return cfg

	post_process_name = cfg.get("post_process")
	if isinstance(post_process_name, str):
		cfg["post_process"] = post_process_map.get(post_process_name)
	return cfg
