import requests

from bs4 import BeautifulSoup



class NewsCollector:



    def get_article_text(
        self,
        url
    ):


        try:

            response = requests.get(
                url,
                timeout=30,
                headers={
                    "User-Agent":
                    "Myanmar-Fact-Verification-Research-Bot/1.0"
                }
            )


            response.raise_for_status()



            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )



            # Remove unnecessary tags

            for tag in soup(
                [
                    "script",
                    "style",
                    "nav",
                    "footer"
                ]
            ):

                tag.decompose()



            paragraphs = soup.find_all(
                "p"
            )



            article = " ".join(

                p.get_text(
                    strip=True
                )

                for p in paragraphs

            )


            return article



        except requests.exceptions.Timeout:

            print(
        "Timeout:",
        url
    )

            return ""


        except requests.exceptions.ConnectionError:

            print(
        "Connection failed:",
        url
    )

            return ""


        except Exception as e:

            print(
        "News collection error:",
        e
    )

            return ""