import json


class SourceManager:


    def __init__(
        self,
        file_path="data/sources.json"
    ):

        self.file_path = file_path



    def load_sources(self):

        with open(
            self.file_path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)



    def get_urls(self):

        sources = self.load_sources()

        return [
            source["url"]
            for source in sources
        ]