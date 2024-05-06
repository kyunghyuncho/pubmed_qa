# we will adapt generate.py from litgpt.
# `load_model` will load litgpt model from a checkpoint directory.
# `generate` will generate from this model given a prompt.

import os
import sys
import time
from pathlib import Path
from typing import Literal, Optional

import lightning as L
import torch
from lightning.fabric.plugins import BitsandbytesPrecision

from litgpt import GPT, Config, PromptStyle, Tokenizer
from litgpt.generate.base import generate
from litgpt.prompts import has_prompt_style, load_prompt_style
from litgpt.utils import CLI, check_valid_checkpoint_dir, get_default_supported_precision, load_checkpoint

# Path to the checkpoint directory
CHECKPOINT_DIR = './checkpoints/google/gemma-2b'

MAX_RETURNED_TOKENS = 1024

# Load the model from the checkpoint directory
def load_model(checkpoint_dir = Path(CHECKPOINT_DIR), 
               max_returned_tokens: int = MAX_RETURNED_TOKENS):
    precision = get_default_supported_precision(training=False)

    fabric = L.Fabric(devices=1, precision=precision, plugins=None)
    fabric.launch()

    check_valid_checkpoint_dir(checkpoint_dir)
    config = Config.from_file(checkpoint_dir / "model_config.yaml")
    checkpoint_path = checkpoint_dir / "lit_model.pth"

    tokenizer = Tokenizer(checkpoint_dir)

    fabric.print(f"Loading model {str(checkpoint_path)!r} with {config.__dict__}", file=sys.stderr)
    
    t0 = time.perf_counter()
    with fabric.init_module(empty_init=True):
        model = GPT(config)
    fabric.print(f"Time to instantiate model: {time.perf_counter() - t0:.02f} seconds.", file=sys.stderr)
    with fabric.init_tensor():
        # set the max_seq_length to limit the memory usage to what we need
        model.max_seq_length = max_returned_tokens
        # enable the kv cache
        model.set_kv_cache(batch_size=1)
    model.eval()

    model = fabric.setup(model)

    t0 = time.perf_counter()
    load_checkpoint(fabric, model, checkpoint_path)
    fabric.print(f"Time to load the model weights: {time.perf_counter() - t0:.02f} seconds.", file=sys.stderr)

    return fabric, model, tokenizer

# create a prompt style
def promptify(instruction: str, 
              question: str,
              context: Optional[str] = None):
    if context is None:
        return f"###### Instruction: {instruction}\n\n###### Question: {question}\n\n###### Answer:"
    else:
        return f"###### Instruction: {instruction}\n\n###### Question: {question}\n\n###### Context: {context}\n\n###### Answer:"

# Generate from the model given a prompt
def generate_candidate(fabric, model, tokenizer, instruction, question, context=None, top_k=10):
    prompt = promptify(instruction, question, context)

    encoded = tokenizer.encode(prompt, device=fabric.device)

    y = generate(model, encoded, MAX_RETURNED_TOKENS, top_k=top_k, eos_id=tokenizer.eos_id)

    output = tokenizer.decode(y)
    # split output at "\n\nAnswer:" and return the second part
    output = output.split("\n\n###### Answer:")[1]
    # # split output at "\n\n" and return the first part
    # output = output.split("\n\n")[0]

    return output.strip()