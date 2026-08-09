import requests
from urllib.parse import urlparse


class URLService:


    def validate_url(self, url):

        try:

            result = urlparse(url)


            if (
                result.scheme not in ["http", "https"]
                or not result.netloc
            ):
                return False


            return True


        except Exception:

            return False



    def get_domain(self, url):

        parsed = urlparse(url)

        return parsed.netloc



    def fetch_content(self, url):

        try:

            response = requests.get(
                url,
                timeout=10,
                headers={
                    "User-Agent":
                    "Mozilla/5.0"
                }
            )


            response.raise_for_status()


            return response.text


        except Exception as e:

            print(
                "URL fetch error:",
                e
            )

            return None