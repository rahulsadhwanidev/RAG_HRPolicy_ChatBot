from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=False)

import os
print("ENV FILE:", find_dotenv() or "<not found>")
k = os.getenv("OPENAI_API_KEY")
print("Key present:", bool(k), "| prefix:", (k[:7] + "...") if k else None)

from openai import OpenAI
OpenAI(api_key=k)  # will raise if key is missing
print("OpenAI client OK")
