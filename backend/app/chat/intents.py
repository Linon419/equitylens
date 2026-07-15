import re

_CONVERSATIONAL_PROMPTS = frozenset(
    {
        "hello",
        "hi",
        "hey",
        "goodmorning",
        "goodafternoon",
        "goodevening",
        "thanks",
        "thankyou",
        "whoareyou",
        "whatcanyoudo",
        "你好",
        "您好",
        "嗨",
        "哈喽",
        "哈啰",
        "哈囉",
        "早上好",
        "下午好",
        "晚上好",
        "早安",
        "晚安",
        "谢谢",
        "感谢",
        "你是谁",
        "你能做什么",
    }
)


def is_conversational_prompt(value: str) -> bool:
    normalized = re.sub(r"[\s!！,.，。?？~～]+", "", value.casefold())
    return normalized in _CONVERSATIONAL_PROMPTS
