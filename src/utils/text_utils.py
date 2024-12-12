def title(text: str):
    if text:
        parts = text.strip().split(" ")
        for i, part in enumerate(parts):
            part = part.strip().upper()
            if len(part) > 3:
                if part.startswith("SD") and (part.endswith("ACE") or part.endswith("AC")):
                    if part.endswith("ACE"):
                        part = part.replace("ACE", "ACe")
                    else:
                        part = part.replace("AC", "ACe")
                elif part.startswith("FA-") or part.startswith("GP"):
                    pass
                else:
                    part = part.capitalize()
            elif part in {"NEW", "OLD", "CAR", "RIO", "PAD"}:
                part = part.capitalize()
            parts[i] = part
        text = " ".join(parts)
    return text
