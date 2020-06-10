import os
import shutil
from json import dumps, JSONEncoder, load, loads
from typing import List, Tuple

import twitter
from markupsafe import escape
from requests import ConnectionError
from twitter.models import Status, TwitterModel, User

from app_secrets import access_token, access_token_secret, consumer_key, consumer_secret
from utils import make_link, remove_none

api = twitter.Api(consumer_key=consumer_key, consumer_secret=consumer_secret, access_token_key=access_token,
                  access_token_secret=access_token_secret, sleep_on_rate_limit=False, cache=None,
                  tweet_mode="extended")


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


def get_statuses_threaded(status_id: int):
    base = get_status(status_id)
    items = [base]
    while getattr(base, "in_reply_to_status_id", None):
        base = get_status(base.in_reply_to_status_id)
        items.append(base)
    return [(item, get_user(item.user.id)) for item in items]


def get_statuses_quoted(status_id: int):
    base = get_status(status_id)
    items = [base]
    while getattr(base, "quoted_status_id", None):
        base = get_status(base.quoted_status_id)
        items.append(base)
    return [(item, get_user(item.user.id)) for item in items]


def generate_status_text(status: Status) -> str:
    base: str = str(escape(status.full_text))
    if status.urls:
        for url in status.urls:
            if url.expanded_url.rstrip("/").split("/")[-1] == getattr(status, "quoted_id_str", ""):
                base = base.replace(url.url, "", 1)
            else:
                base = base.replace(url.url, make_link(url.expanded_url), 1)
    base = base.strip()
    if status.user_mentions:
        for user in status.user_mentions:
            base = base.replace("@" + user.screen_name, "", 1)
    if status.media:
        for media in status.media:
            if media.type == "photo":
                base += f' <img src="{media.media_url_https}">'
                base = base.replace(media.url, "", 1)
            elif media.type in ["video", "animated_gif"]:
                type_str = "<video "
                if media.type == "video":
                    type_str += "controls autoplay"
                elif media.type == "animated_gif":
                    type_str += "autoplay loop"
                type_str += ">"
                for variant in media.video_info["variants"]:
                    type_str += f'<source src="{variant["url"]}" type="{variant["content_type"]}">'
                base += type_str + f'<a href="{media.expanded_url}">{media.display_url}</a>' + "</video>"
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
