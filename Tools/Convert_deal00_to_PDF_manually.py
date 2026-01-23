#!/usr/bin/env python3
import os
from weasyprint import HTML

# Define the source root folder and the destination folder for PDFs
source_root = '/Users/rick/Documents/Bridge/Baker Bridge/Website/Baker Bridge/bakerbridge.coffeecup.com'
dest_folder = '/Users/rick/Documents/Bridge/Baker Bridge/Tools/pdfs'

# Create the destination folder if it doesn't exist
os.makedirs(dest_folder, exist_ok=True)

# Walk through the source directory tree
for root, dirs, files in os.walk(source_root):
    for file in files:
        if file.lower() == "deal00.html":
            html_path = os.path.join(root, file)
            relative_dir = os.path.relpath(root, source_root)
            pdf_name = "root.pdf" if relative_dir == '.' else relative_dir.replace(os.sep, "_") + ".pdf"
            pdf_path = os.path.join(dest_folder, pdf_name)
            print(f"Converting '{html_path}' to '{pdf_path}'")

            try:
                # Inject print-style override
                with open(html_path, 'r') as f:
                    soup = BeautifulSoup(f.read(), "html.parser")

                style_tag = soup.new_tag("style", media="print")
                style_tag.string = """
                    * {
                        background: none !important;
                        background-color: transparent !important;
                    }
                """
                soup.head.append(style_tag)

                # Convert modified HTML to PDF
                HTML(string=str(soup)).write_pdf(pdf_path)
                print(f"Successfully created '{pdf_path}'")

            except Exception as e:
                print(f"Error converting '{html_path}': {e}")