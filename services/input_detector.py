import re



class InputDetector:


    def is_url(self, text):


        pattern = r"^https?://"


        return bool(
            re.match(
                pattern,
                text.strip()
            )
        )