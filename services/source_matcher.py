from difflib import SequenceMatcher



class SourceMatcher:


    def calculate_similarity(
        self,
        claim,
        article
    ):


        claim_words = set(
            claim.split()
        )


        article_words = set(
            article.split()
        )


        common = (
            claim_words &
            article_words
        )


        if len(claim_words) == 0:

            return 0



        score = (
            len(common)
            /
            len(claim_words)
        )


        return round(
            score * 100,
            2
        )



    def match_sources(
        self,
        claim,
        sources
    ):


        results = []


        for source in sources:


            score = self.calculate_similarity(
                claim,
                source["text"]
            )


            results.append({

                "source":
                source["name"],

                "score":
                score

            })


        results.sort(
            key=lambda x:x["score"],
            reverse=True
        )


        return results