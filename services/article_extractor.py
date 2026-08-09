from bs4 import BeautifulSoup



class ArticleExtractor:


    def extract(self, html):

        try:

            soup = BeautifulSoup(
                html,
                "html.parser"
            )


            # Title

            title = ""

            if soup.title:

                title = soup.title.text.strip()



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



            # Extract text

            text = soup.get_text(
                separator="\n"
            )


            lines = []


            for line in text.split("\n"):

                line = line.strip()


                if len(line) > 20:

                    lines.append(line)



            content = "\n".join(lines)



            return {

                "title": title,

                "content": content

            }



        except Exception as e:


            print(
                "Extraction error:",
                e
            )


            return None