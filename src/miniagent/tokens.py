from __future__ import annotations
from pyexpat.errors import messages 
import tiktoken
from tiktoken import model
from miniagent.types import Message
from anthropic import AsyncAnthropic

from dotenv import load_dotenv
load_dotenv()

def count_tokens_openai(messages: list[Message], model: str) -> int:
    """
    Count the number of tokens in a list of messages for OpenAI models.
    Args:
        messages (list[Message]): The list of messages to count tokens for.
        model (str): The model name to use for tokenization.
    Returns:
        int: The total number of tokens in the messages.
    """
    encoding = tiktoken.encoding_for_model(model) # pick the right encoding for the model
    total = 0
    for msg in messages:
        total += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
        for block in msg.content:
            if block.type == "text":
                total += len(encoding.encode(block.text))

    total += 2  # every reply is primed with <im_start>assistant<im_end>\n
    return total    

_anthropic = AsyncAnthropic()

async def count_tokens_anthropic(messages: list[Message], model: str) -> int:
    """
    Count the number of tokens in a list of messages for Anthropic models. 
    This costs a small amount of money because it makes an API call to the Anthropic service, but it is more accurate than using tiktoken.
    Args:
        messages (list[Message]): The list of messages to count tokens for.
        model (str): The model name to use for tokenization.
    Returns:
        int: The total number of tokens in the messages.
    """
    result = await _anthropic.messages.count_tokens( # count_tokens is a method provided by the Anthropic API to count tokens in messages.
        model=model,
        messages=[m.model_dump() for m in messages], # model_dump() converts the Message object to a dictionary that can be serialized to JSON
    )
    return result.input_tokens