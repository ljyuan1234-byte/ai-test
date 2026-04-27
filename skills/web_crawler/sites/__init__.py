from .autohome import fetch_news_list as autohome_fetch, fetch_article_content as autohome_content
from .dongchedi import fetch_news_list as dongchedi_fetch, fetch_article_content as dongchedi_content

__all__ = [
    "autohome_fetch",
    "autohome_content",
    "dongchedi_fetch",
    "dongchedi_content",
]
