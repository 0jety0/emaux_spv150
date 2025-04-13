import re


def camel_to_snake(camel_str: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", camel_str).lower()
