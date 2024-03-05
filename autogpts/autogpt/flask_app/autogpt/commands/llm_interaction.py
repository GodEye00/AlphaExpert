"""Commands to get response from an llm"""

COMMAND_CATEGORY = "ask_llm"
COMMAND_CATEGORY_TITLE = "Ask LLM"

import io
import json
import logging
import time
import uuid
from base64 import b64decode

import openai
import requests
from PIL import Image

from autogpt.agents.agent import Agent
from autogpt.command_decorator import command
from autogpt.core.utils.json_schema import JSONSchema

logger = logging.getLogger(__name__)


@command(
    "generate_code",
    "Generates python code",
    {
        "prompt": JSONSchema(
            type=JSONSchema.Type.STRING,
            description="The prompt used to generate the code",
            required=True,
        ),
    },
    lambda config: bool(config.smart_llm) or bool(config.fast_llm),
    "Requires an llm  to be set.",
)
def generate_code(prompt: str, agent: Agent) -> str:
    """Generate python code from a prompt.

    Args:
        prompt (str): The prompt to use

    Returns:
        str: The code generated
    """

    # GPT3 or GPT4
    if agent.legacy_config.smart_llm or agent.legacy_config.fast_llm:
        return ask_openai(prompt, agent)
    return "No llm model found."


def ask_openai(prompt: str, agent: Agent) -> str:
    """Generate response from openai gpt3.5 or gpt4 models.

    Args:
        prompt (str): The prompt to use

    Returns:
        str: Response from openai gpt3.5 or gpt4 model
    """
    logging.info(f"About to ask openai model for an answer. Prompt: {prompt}")
    try:
        gpt4 = agent.legacy_config.smart_llm
        gpt3 = agent.legacy_config.smart_llm
        response = openai.Completion.create(
            model= gpt4 if gpt4 else gpt3,
            temperature=0.4,
            messages=prompt
        )
        response_text = response.choices[0].text
        response_to_send = {"role": "assistant", "content": response_text}
        return response_to_send
    except Exception as e:
        logging.exception(f"Error in GPT API call: {e}")
        raise "Sorry, an error occurred while getting response from openai models."
    
    