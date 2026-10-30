"""Small offline guard for keeping Do's inputs English-only."""

import re


_NON_ENGLISH_STRONG = {
    # Common Hindi / Hinglish words, including phrases seen in the voice log.
    "aap", "bhi", "dena", "dene", "hai", "hain", "ho", "jhooth", "kar",
    "karo", "kya", "logon", "mujhe", "padenge", "rahe", "rupaye", "sikke",
    "yahan", "wahan", "kyun", "kaise", "mera", "mere", "meri", "tum", "tumhe",
    "bhai", "yaar", "abhi", "nahin", "nahi", "chalo", "chaliye", "accha", "acha",
    "theek", "thik", "sahi", "hoon", "hun", "batao", "suno", "dekho", "kahan",
    # Common markers from other languages written with Latin letters.
    "bonjour", "merci", "gracias", "hola", "adios", "porfavor", "guten", "danke",
    "ciao", "obrigado", "obrigada", "bueno", "buenos", "hablo", "ingles", "gusta",
    "musica", "quiero", "necesito", "donde", "cuando", "porque", "eres", "estas",
    "vamos", "muchas", "quero", "estou", "muito", "falar", "buongiorno", "grazie",
    "capisco", "voglio", "spreche", "deutsch", "comment", "allez", "pouvez", "parle",
    "comprends", "francais", "bonsoir", "tal", "eu", "sou", "stai", "bon", "ik",
    "ben", "hej", "merhaba", "salam", "privet", "konnichiwa", "annyeong", "ni",
    "hao", "adeus", "sayonara", "arigato",
}

_NON_ENGLISH_CONTEXT = {
    "aun", "avec", "bien", "como", "con", "der", "des", "din", "el", "ella",
    "es", "esta", "estoy", "et", "guten", "ich", "ist", "je", "la", "le",
    "los", "mais", "mon", "ne", "que", "qui", "una", "und", "vous", "wir",
    "yo", "ko", "bol", "ek", "log", "paas", "rahe", "uska",
    "pas", "non", "ich", "nicht", "bitte", "como", "esta", "estoy", "soy", "para",
    "puedes", "usted", "nosotros", "por", "dias", "buenas", "voce", "fala", "com",
    "sono", "puoi", "mi", "per", "favore", "spreche", "wie", "haben", "heisse",
    "je", "suis", "avec", "moi", "est", "nao", "entendo", "abrir", "fecha", "quieres",
    "quer", "haces", "tienes", "estamos", "vorrei",
}


def is_english_text(text: str) -> bool:
    """Reject non-Latin scripts and common non-English words without network calls."""
    value = str(text or "").strip()
    if any(character.isalpha() and ord(character) > 127 for character in value):
        return False

    words = re.findall(r"[a-z]+", value.lower())
    if not words:
        return True
    if any(word in _NON_ENGLISH_STRONG for word in words):
        return False
    return sum(word in _NON_ENGLISH_CONTEXT for word in words) < 2
