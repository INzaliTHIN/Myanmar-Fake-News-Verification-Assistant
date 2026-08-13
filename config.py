import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    SECRET_KEY = os.getenv(
        "SECRET_KEY"
    )

    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///database.db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEEPSEEK_API_KEY = os.getenv(
        "DEEPSEEK_API_KEY"
    )


    HF_TOKEN = os.getenv(
        "HF_TOKEN"
    )


    GOOGLE_API_KEY = os.getenv(
        "GOOGLE_API_KEY"
    )


    GOOGLE_CSE_ID = os.getenv(
        "GOOGLE_CSE_ID"
    )