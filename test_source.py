from services.source_manager import SourceManager



manager = SourceManager()


sources = manager.load_sources()


for source in sources:

    print(
        source["name"],
        "-",
        source["trust_score"]
    )