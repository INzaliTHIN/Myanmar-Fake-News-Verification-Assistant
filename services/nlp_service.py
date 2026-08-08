import re


class MyanmarTextProcessor:


    def normalize_text(self, text):

        if not text:
            return ""


        # Remove extra spaces
        text = re.sub(
            r"\s+",
            " ",
            text
        )


        # Remove unwanted symbols
        text = re.sub(
            r"[^\u1000-\u109F\s\w]",
            "",
            text
        )


        return text.strip()



    def clean_text(self, text):

        text = self.normalize_text(
            text
        )


        # Lower space normalization
        text = text.replace(
            "\n",
            " "
        )


        return text



    def sentence_split(self, text):

        sentences = re.split(
            r"[။!?]",
            text
        )


        return [
            s.strip()
            for s in sentences
            if s.strip()
        ]



    def process(self, text):

        cleaned = self.clean_text(
            text
        )


        sentences = self.sentence_split(
            cleaned
        )


        return {

            "original": text,

            "cleaned": cleaned,

            "sentences": sentences

        }