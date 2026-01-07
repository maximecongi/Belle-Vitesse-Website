import markdown
from markupsafe import Markup

def markdown_filter(text):
    if not text:
        return ""
    return Markup(
        markdown.markdown(
            text,
            extensions=["extra", "sane_lists"]
        )
    )