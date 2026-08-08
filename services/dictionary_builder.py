import os
import re



class DictionaryBuilder:


    def extract_words(self, text):

        text = re.sub(
            r"[။၊!?]",
            " ",
            text
        )


        words = re.findall(
            r'[\u1000-\u109F]+',
            text
        )


        return words



    def split_compound_words(self, words):

        result = set()


        suffixes = [

            "တွင်",
            "မှ",
            "သည်",
            "များ",
            "နှင့်",
            "ဆိုင်ရာ"

        ]


        for word in words:


            for suffix in suffixes:


                if word.endswith(suffix):

                    base = word[:-len(suffix)]

                    if len(base) >= 2:

                        result.add(base)


                    result.add(suffix)

                    break


            else:

                if len(word) >= 2:

                    result.add(word)



        return result



    def load_existing(
        self,
        file_path
    ):

        if not os.path.exists(file_path):

            return set()


        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:


            return set(

                line.strip()

                for line in file

                if line.strip()

            )



    def update_dictionary(
        self,
        text,
        output_file="data/myanmar_words.txt"
    ):


        folder = os.path.dirname(
            output_file
        )


        if folder:

            os.makedirs(
                folder,
                exist_ok=True
            )


        words = self.extract_words(
            text
        )


        new_words = self.split_compound_words(
            words
        )


        old_words = self.load_existing(
            output_file
        )


        all_words = old_words.union(
            new_words
        )


        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as file:


            for word in sorted(all_words):

                file.write(
                    word + "\n"
                )


        return len(all_words)