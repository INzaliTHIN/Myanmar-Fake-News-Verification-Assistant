import os
import requests



class DeepSeekService:


    def __init__(self):

        self.api_key = os.getenv(
            "DEEPSEEK_API_KEY"
        )

        self.url = (
            "https://api.deepseek.com/chat/completions"
        )


    def analyze_claim(
        self,
        claim,
        evidence
    ):


        if not self.api_key:

            return {
                "error":
                "API key missing"
            }



        headers = {

            "Authorization":
            f"Bearer {self.api_key}",

            "Content-Type":
            "application/json"

        }



        prompt = f"""

You are a Myanmar fake news verification assistant.

Analyze this claim:

CLAIM:
{claim}


Evidence:
{evidence}


Return:

1. Is this claim likely true or false?
2. Explain why.
3. Give confidence percentage.

"""



        data = {

            "model":
            "deepseek-chat",

            "messages":[

                {
                    "role":"user",
                    "content":prompt
                }

            ],

            "temperature":0.2

        }



        response = requests.post(

            self.url,

            headers=headers,

            json=data,

            timeout=30

        )



        if response.status_code !=200:

            return{
                "status": "failed",
                "code": response.status_code,
                "message": response.text
            }



        result = response.json()



        return result[
            "choices"
        ][0][
            "message"
        ][
            "content"
        ]