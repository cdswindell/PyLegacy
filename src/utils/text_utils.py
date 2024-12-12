def title(text: str):
    if text:
        parts = text.strip().split(" ")
        for i, part in enumerate(parts):
            part = part.strip().upper()
            if len(part) > 3:
                if part.startswith("SD") and part.endswith("ACE"):
                    part = part.replace("ACE", "ACe")
                else:
                    part = part.capitalize()
                parts[i] = part
            text = " ".join(parts)
    return text
