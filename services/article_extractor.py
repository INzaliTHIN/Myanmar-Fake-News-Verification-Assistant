import requests

from bs4 import BeautifulSoup

from urllib.parse import urljoin



class ArticleExtractor:


    def get_article_links(
        self,
        url,
        limit=5
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


            links = []


            for a in soup.find_all("a", href=True):


                link = urljoin(
                    url,
                    a["href"]
                )


                if link not in links:

                    links.append(
                        link
                    )


                if len(links) >= limit:

                    break



            return links



        except Exception as e:


            print(
                "Article link error:",
                e
            )


            return []