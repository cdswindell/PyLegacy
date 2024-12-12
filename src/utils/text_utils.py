def title(text: str):
    if text:
        parts = text.strip().split(" ")
        for i, part in enumerate(parts):
            if len(part) > 3:
                parts[i] = part.capitalize()
            text = " ".join(parts)
    return text
