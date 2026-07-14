import re
import unicodedata

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize_name(name: str) -> str:
    """Lowercase, strip accents/punctuation/suffixes so a name from balldontlie
    (e.g. 'Nikola Jokic') and a name from nba_api (e.g. 'Nikola Jokić') compare equal.
    """
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii").lower()
    ascii_name = re.sub(r"[.\-']", " ", ascii_name)
    tokens = [t for t in ascii_name.split() if t not in SUFFIXES]
    return " ".join(tokens).strip()
