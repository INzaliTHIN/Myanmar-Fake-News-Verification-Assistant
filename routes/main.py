from flask import Blueprint, redirect
from flask import render_template
from flask import url_for

main = Blueprint("main", __name__)

@main.route("/")
def home():

    return redirect(
        url_for("chat.new_chat")
    )
