import os
import shutil
from json import dumps, JSONEncoder, load, loads
from re import compile
from typing import List, Tuple

import twitter
from requests import ConnectionError
from twitter.models import Status, TwitterModel, User

from app_secrets import access_token, access_token_secret, consumer_key, consumer_secret
from utils import make_link, remove_none, url_left_part

api = twitter.Api(consumer_key=consumer_key, consumer_secret=consumer_secret, access_token_key=access_token,
                  access_token_secret=access_token_secret, sleep_on_rate_limit=False, cache=None,
                  tweet_mode="extended")

hashtag = compile(r"#([A-Za-z0-9_]+)")


class TwitterModelEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, TwitterModel):
            base = {key: value for key, value in o.AsDict().items() if
                    value is not None and key not in ["param_defaults", "_json"]}
            extras = {key: value for key, value in o._json.items() if "entities" in key}
            base.update(extras)
            return base
        else:
            return super().default(o)


def init_cache(itemtype: str):
    if not os.path.exists("cache"):
        os.mkdir("cache")
    if not os.path.exists(f"cache/{itemtype}"):
        os.mkdir(f"cache/{itemtype}")


def get_cache(itemtype: str, item_id: int) -> dict:
    init_cache(itemtype)
    if not os.path.exists(f"cache/{itemtype}/{item_id}.json"):
        return
    else:
        with open(f"cache/{itemtype}/{item_id}.json", "r") as fp:
            return load(fp)


def write_cache(item_type: str, obj: object) -> dict:
    init_cache(item_type)
    with open(f"cache/{item_type}/{obj.id}.json", "w") as fp:
        json = dumps(obj, cls=TwitterModelEncoder)

        fp.write(json)
    return loads(json)


def get_status(status_id: int) -> Status:
    cache = get_cache("status", status_id)
    retries = 0
    if cache is None:
        print("Making network request for status id %s" % status_id)
        while True:
            try:
                data = api.GetStatus(status_id, trim_user=True)
                break
            except ConnectionError:
                retries += 1
                if retries > 1:
                    raise
        cache = write_cache("status", data)
    return Status.NewFromJsonDict(cache)


def get_user(user_id: int) -> User:
    cache = get_cache("user", user_id)
    retries = 0
    if cache is None:
        print("Making network request for user id %s" % user_id)
        while True:
            try:
                data = api.GetUser(user_id)
                break
            except ConnectionError:
                retries += 1
                if retries > 1:
                    raise
        cache = write_cache("user", data)
    return User.NewFromJsonDict(cache)


def regenerate_user_cache():
    init_cache("user")
    shutil.rmtree("cache/user")


def get_statuses_threaded(status_id: int, callstack: int = 0):
    base = get_status(status_id)
    if callstack >= 10:
        return []
    items = [base]
    while getattr(base, "in_reply_to_status_id", None):
        base = get_status(base.in_reply_to_status_id)
        items.append(base)
    extras = [item1 for item1, item2 in get_statuses_quoted(items[-1].id, callstack=callstack + 1)]
    items.extend(extras)
    return [(item, get_user(item.user.id)) for item in remove_duplicates(items)]


def get_statuses_quoted(status_id: int, callstack: int = 0):
    base = get_status(status_id)
    if callstack >= 10:
        return []
    items = [base]
    while getattr(base, "quoted_status_id", None):
        base = get_status(base.quoted_status_id)
        items.append(base)
    extras = [item1 for item1, item2 in get_statuses_threaded(items[-1].id, callstack=callstack + 1)]
    items.extend(extras)
    return [(item, get_user(item.user.id)) for item in remove_duplicates(items)]


def generate_status_text(status: Status) -> str:
    base: str = hashtag.sub(r'<a href="https://twitter.com/hashtag/\1?src=hashtag_click" target="_blank">#\1</a>',
                            status.full_text)
    if status.urls:
        for url in status.urls:
            print(url.url, url.expanded_url)
            if url.expanded_url.rstrip("/").split("/")[-1] == (
                    getattr(status, "quoted_id_str", None) or getattr(status, "quoted_status_id_str", None) or ""):
                base = base.replace(url.url, "", 1)
            else:
                base = base.replace(url.url, make_link(url.expanded_url), 1)
    base = base.strip()
    if status.user_mentions:
        for user in status.user_mentions:
            if base.lstrip().startswith("@"):
                base = base.replace("@" + user.screen_name, "", 1)
            else:
                break
    if status.media:
        if not base.rstrip().endswith("<br />"):
            base += "<br />"
        for media in status.media:
            if media.type == "photo":
                base += f' <img src="{media.media_url_https}">'
                base = base.replace(media.url, "", 1)
            elif media.type in ["video", "animated_gif"]:
                type_str = "<video autoplay loop"
                if media.type == "video":
                    type_str += " controls"
                type_str += ">"
                for variant in media.video_info["variants"]:
                    type_str += f'<source src="{variant["url"]}" type="{variant["content_type"]}">'
                base += type_str + f'<a href="{media.expanded_url}">{url_left_part.sub("", media.display_url)}</a>' + \
                        "</video>"
                base = base.replace(media.url, "", 1)
    return base


def user_status_list(item_list: List[Tuple[Status, User]]) -> Tuple[List[User], List[Status]]:
    item_list.reverse()
    original_status, original_user = item_list.pop(0)
    users = [original_user]
    statuses = [original_status]
    for status, user in item_list:
        statuses.append(status)
        if user.id == remove_none(users)[-1].id:
            users.append(None)
        else:
            users.append(user)
    return users, statuses


def get_unique_users(user_list: List[User]) -> List[User]:
    user_list = remove_none(user_list)
    final = {}
    for user in user_list:
        final[user.id] = user
    return [user for userid, user in final.items()]


def remove_duplicates(item_list: list) -> list:
    final = [item_list.pop(0)]
    for item in item_list:
        if item.id != final[-1].id:
            final.append(item)
    return final
