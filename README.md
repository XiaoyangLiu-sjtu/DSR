# [ICML 2026] DSR

📝 Official implementation for the paper:

[Decompose, Structure, and Repair: A Neuro-Symbolic Framework for Autoformalization via Operator Trees](https://arxiv.org/pdf/2604.19000)


## Dataset and Model Downloads
The DSR Formalizer and the training dataset used in this paper are publicly available at the following repository: [🤗 HuggingFace](https://huggingface.co/collections/XiaoyangLiu-sjtu/dsr).


## Project Structure
The repository is organized as follows.

```text
DSR/
├── benchmark/                          # Benchmark datasets
│   ├── proverbench.json
│   ├── proofnet.jsonl
│   ├── prime.json
│   ├── fate_x.json
│   ├── fate_h.json
│   └── fate_m.json
├── configs/                            # Model and prompt configs
│   ├── config_model.py                 # Model registry, inference types, decoding configs
│   └── config_prompt.py                # Prompt templates for decomposition/repair/evaluation
├── src/                                # Core pipeline modules
│   ├── decomposer.py                   # NL statement -> conditions/conclusion decomposition
│   ├── structurer.py                   # Component-level formalization with operator-tree outputs
│   ├── repairer.py                     # Local/global repair and theorem splicing utilities
│   └── evaluator.py                    # Lean compile + LeanScorer evaluation and reporting
├── main.py                             # End-to-end pipeline entry (decompose/structure/repair/evaluate)
├── utils.py                            # Shared utilities: model wrappers, Lean scheduler, I/O, logging
├── LICENSE
└── README.md
```


## Quick Start
1. **Install Lean4.** Follow the official [Lean4 installation guide](https://leanprover-community.github.io/get_started.html).
2. **Clone the repository.** Clone this repository and enter the project directory.
3. **Set up runtime dependencies.** Install Python dependencies (`openai`, `vllm`, `transformers`, `tqdm`) and configure model/API settings in `configs/config_model.py` and `utils.py` (for `api_key` / `base_url`).
4. **Run the pipeline.** The main entry point is:
    - `main.py`: Runs the DSR pipeline across configured benchmarks/models, including decomposition, structured translation, optional repair, Lean compilation, and LeanScorer evaluation.
        ```shell
        # Entry: end-to-end run
        python main.py
        ```


## Citation
```bibtex
@inproceedings{liu2026decompose,
title={Decompose, Structure, and Repair: A Neuro-Symbolic Framework for Autoformalization via Operator Trees},
author={Xiaoyang Liu and Zineng Dong and Yifan Bai and Yantao Li and Yuntian Liu and Tao Luo},
booktitle={Forty-third International Conference on Machine Learning},
year={2026},
url={https://openreview.net/forum?id=b9PBqFgXp6}
}
```


## Contact
Feel free to discuss the paper/data/code with us through issues/emails!
- Xiaoyang Liu: xiaoyang.liu@sjtu.edu.cn
