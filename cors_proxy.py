import http.server
import sys
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO

from PIL import Image

TARGET_PREFIX = "https://okn-mk.mkrf.ru"


class ProxyHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse the URL to get the target URL
        parsed_path = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_path.query)
        target_url = query.get("url", [None])[0]

        if not target_url or not target_url.startswith(TARGET_PREFIX):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"URL parameter is missing")
            return

        try:
            # Send a GET request to the target URL
            with urllib.request.urlopen(target_url) as response:
                # Read the response content
                content = response.read()
                content_type = response.info().get_content_type()

                if content_type.startswith("image/"):
                    # Resize the image
                    image = Image.open(BytesIO(content))
                    resized_image = self.resize_image(image)
                    output = BytesIO()
                    resized_image.save(output, format=image.format)
                    content = output.getvalue()

                # Send the response headers
                self.send_response(response.status)
                self.send_header("Content-Type", content_type)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                # Write the response content
                self.wfile.write(content)
        except urllib.error.URLError as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error fetching the resource: {e}".encode("utf-8"))

    def resize_image(self, image, max_size=(800, 800)):
        # Calculate the new size maintaining the aspect ratio
        image.thumbnail(max_size, Image.LANCZOS)
        return image


def run(port: int):
    server_address = ("", port)
    httpd = http.server.HTTPServer(server_address, ProxyHTTPRequestHandler)
    print(f"Starting proxy server on port {port}...")
    httpd.serve_forever()


if __name__ == "__main__":
    target_port = int(sys.argv[1]) if len(sys.argv) > 1 else 8805
    run(target_port)
