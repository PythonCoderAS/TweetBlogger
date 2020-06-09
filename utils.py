from functools import partial

def username_html(prefix: str, username: str, symbol: str = "@") -> str:
    return f'<a href="{prefix}{username}" target="_blank" class="normal_text underline_on_hover">{symbol}{username}</a>'


def remove_none(item_list: list) -> list:
    return [item for item in item_list if item is not None]

def make_link(link: str) -> str:
    return f'<a href="{link}" target="_blank">{link}</a>'

twitter_username = partial(username_html, "https://www.twitter.com/")
github_username = partial(username_html, "https://www.github.com/")