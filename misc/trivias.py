import requests
import random


def get_trivia():
    """
    Fetch a trivia from uselessfacts API.
    If request fails, return a fallback message.
    """
    try:
        response = requests.get(
            "https://uselessfacts.jsph.pl/api/v2/facts/random?language=en", timeout=10
        )
        if 200 <= response.status_code < 300:
            data = response.json()
            return data.get("text", "DYK? Coding is 10% writing and 90% debugging.")
        else:
            return "DYK? Sometimes APIs nap too!"
    except Exception:
        fallback_trivias = [
            "DYK? The first computer bug was an actual moth stuck in a relay.",
            "DYK? Email existed before the World Wide Web.",
            "DYK? The first 1GB hard drive (1980) weighed over 500 pounds.",
        ]
        return random.choice(fallback_trivias)
