from Levenshtein import distance
import os


class MyanmarSpellChecker:


    def __init__(
        self,
        dictionary_path="data/myanmar_words.txt"
    ):

        print("INIT RUNNING")

        self.dictionary_path = dictionary_path

        self.dictionary = []

        self.load_dictionary()



    def load_dictionary(self):

        if not os.path.exists(
            self.dictionary_path
        ):

            print(
                "Dictionary not found"
            )

            return


        with open(
            self.dictionary_path,
            "r",
            encoding="utf-8"
        ) as file:

            self.dictionary = [

                line.strip()

                for line in file

                if line.strip()

            ]


        print(
            "Loaded words:",
            len(self.dictionary)
        )



    def find_correction(
        self,
        word
    ):

        if not self.dictionary:

            return None


        best = None

        score_min = 999


        for item in self.dictionary:

            score = distance(
                word,
                item
            )


            if score < score_min:

                score_min = score

                best = item



        if score_min <= 2:

            return {

                "original": word,

                "suggestion": best,

                "distance": score_min

            }


        return None



    def check_text(
        self,
        text
    ):

        results = []


        for word in text.split():

            correction = self.find_correction(
                word
            )


            if correction:

                results.append(
                    correction
                )


        return results