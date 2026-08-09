from services.url_service import URLService


service = URLService()


url = "https://www.bbc.com"


print(
    "Valid:",
    service.validate_url(url)
)


print(
    "Domain:",
    service.get_domain(url)
)


content = service.fetch_content(url)


if content:

    print(
        "HTML length:",
        len(content)
    )

else:

    print(
        "No content"
    )