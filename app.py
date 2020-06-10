import os
import sys
import tarfile
from itertools import count
from re import compile

import pdfkit
from flask import abort, Flask, redirect, render_template, request, send_file
from twitter.error import TwitterError
from database_operations import setup_db

from twitter_api import generate_status_text, get_statuses_quoted, get_statuses_threaded, get_unique_users, \
    user_status_list
from utils import github_username, remove_none, twitter_username

app = Flask(__name__)


if "darwin" in sys.implementation._multiarch:
    config = pdfkit.configuration(wkhtmltopdf="/usr/local/bin/wkhtmltopdf")
else:
    config = pdfkit.configuration(wkhtmltopdf=os.path.abspath(os.path.join(__file__, "..", "wkhtmltopdf-heroku")))

status_url = compile(r"https://([\S]+\.twitter\.com|twitter\.com)/[\S]+/status/([0-9]+)")

@app.context_processor
def bootstrap_functions():
    return {'twitter_username'    : twitter_username,
            'github_username'     : github_username,
            "remove_none"         : remove_none,
            "get_unique_users"    : get_unique_users,
            "generate_status_text": generate_status_text,
            "count"               : count}


@app.context_processor
def load_builtins():
    return {key: value for key, value in __builtins__.items() if not key.startswith("_")}


@app.route("/", methods=["GET"])
def homepage():
    return render_template("homepage.html")


@app.route("/about", methods=["GET"])
def about():
    return render_template("about.html")


@app.route("/thread/<int:status_id>")
def process_thread(status_id: int, pdf=False):
    try:
        users, statuses = user_status_list(get_statuses_threaded(status_id))
    except TwitterError as err:
        if err.args[0][0]['code'] == 144:
            return render_template("404.html", status=status_id), 404
        else:
            raise
    return render_template("status.html", users=users, statuses=statuses, status_id=status_id, type="thread", pdf=pdf)


@app.route("/retweet/<int:status_id>")
def process_retweet(status_id: int, pdf=False):
    try:
        users, statuses = user_status_list(get_statuses_quoted(status_id))
    except TwitterError as err:
        if err.args[0][0]['code'] == 144:
            return render_template("404.html", status=status_id), 404
        else:
            raise
    return render_template("status.html", users=users, statuses=statuses, status_id=status_id, type="retweet", pdf=pdf)


@app.route("/pdf/thread/<int:item_id>")
def generate_pdf_thread(item_id: int):
    return generate_pdf(process_thread(item_id, pdf=True), item_id)


@app.route("/pdf/retweet/<int:item_id>")
def generate_pdf_retweet(item_id: int):
    return generate_pdf(process_retweet(item_id, pdf=True), item_id)


def generate_pdf(data: str, item_id: int):
    if data[-1] == 404:
        return data
    pdfkit.from_string(data, "out.pdf", configuration=config)
    return send_file("out.pdf", as_attachment=True, attachment_filename=f"{item_id}.pdf")


@app.route("/action", methods=["POST"])
def action():
    action_type = request.form.get("type", "thread")
    status_id: str = request.form.get("status", "")
    match = status_url.search(status_id.strip())
    if not status_id or not (status_id.isnumeric() or match):
        return abort(400)
    if match:
        status_id = match.group(2)
    if action_type == "thread":
        return redirect(f"/thread/{status_id}")
    elif action_type == "retweet":
        return redirect(f"/retweet/{status_id}")
    else:
        return abort(400)


@app.route("/get_cache")
def get_cache():
    with tarfile.open("cache.tar.gz", "w:gz") as tf:
        tf.add("cache")
    return send_file("cache.tar.gz", as_attachment=True)


@app.errorhandler(400)
def deal_400(*_a):
    return render_template("400.html")


@app.errorhandler(500)
def deal_500(*_a):
    return render_template("500.html")


@app.errorhandler(404)
def deal_404(*_a):
    return render_template("404.html")

if __name__ == '__main__':
    app.run()
