POPUP_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dynamic Resource Renderer</title>
    <style>
        body {{
            font-family: 'Lato', 'Helvetica Neue', Arial, Helvetica, sans-serif;
        }}
        #content img {{
            max-width: 100%;
            max-height: 100%;
            width: auto;
            height: auto;
        }}
        #content {{
            width: 100%;
            height: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }}
    </style>
</head>
<body>
    <div><h4>{title}</h4></div>
    <div>{description}</div>
    <div id="content"></div>

    <script>
    async function fetchAndRender(url) {{
        try {{
            const response = await fetch(url);
            const contentType = response.headers.get('Content-Type');
            const contentDiv = document.getElementById('content');
            contentDiv.innerHTML = '';

            if (contentType.startsWith('image/') || contentType === 'application/octet-stream') {{
                // If the content is an image or octet-stream (assuming it's a jpg image)
                const blob = await response.blob();
                const img = document.createElement('img');
                img.src = URL.createObjectURL(blob);
                contentDiv.appendChild(img);
            }}
        }} catch (error) {{
            console.error('Error fetching the resource:', error);
        }}
    }}
    const mediaUrl = {media_url};
    if (mediaUrl) {{
        fetchAndRender(mediaUrl);
    }}
    </script>
</body>
</html>"""

CORS_PROXY_URL = "https://collectivism.ovh/okn-proxy?url={}"


def add_cors_proxy_prefix(url: str) -> str:
    return CORS_PROXY_URL.format(url)


def wrap_in_quotes(val: str) -> str:
    return f"'{val}'"


def format_description(
    *,
    verbose_address: str | None,
    okn_category: str | None,
    okn_type: str | None,
    historical_date: str | None,
) -> str:
    description_items = (
        verbose_address and f"Адрес: {verbose_address}",
        okn_type and f"Вид: {okn_type}",
        okn_category and f"Категория: {okn_category}",
        historical_date and f"Дата создания: {historical_date}",
    )

    return "<br/>".join(item for item in description_items if item)


def format_popup_html(*, title: str, description: str, media_url: str | None) -> str:
    media_url_or_undef = wrap_in_quotes(add_cors_proxy_prefix(media_url)) or "undefined"
    return POPUP_TEMPLATE.format(
        title=title, description=description, media_url=media_url_or_undef
    )
