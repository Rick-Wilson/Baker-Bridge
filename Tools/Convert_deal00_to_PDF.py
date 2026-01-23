#!/usr/bin/env python3
import os
from bs4 import BeautifulSoup
from weasyprint import HTML

# Define source and destination folders (relative to script location in Tools/)
script_dir = os.path.dirname(os.path.abspath(__file__))
source_root = os.path.join(script_dir, '..', 'Website', 'Baker Bridge', 'bakerbridge.coffeecup.com')
dest_folder = os.path.join(script_dir, 'pdfs')

# Create destination folder if it doesn't exist
os.makedirs(dest_folder, exist_ok=True)

def style_suit_symbols(soup):
    """
    Replaces ♥ and ♦ symbols with span-wrapped red versions.
    """
    for text_node in soup.find_all(string=True):
        if '♥' in text_node or '♦' in text_node:
            new_text = (
                text_node.replace('♥', '<span class="red-suit">♥</span>')
                         .replace('♦', '<span class="red-suit">♦</span>')
            )
            text_node.replace_with(BeautifulSoup(new_text, 'html.parser'))

# Walk the source directory
for root, dirs, files in os.walk(source_root):
    for file in files:
        if file.lower() == "deal00.html":
            html_path = os.path.join(root, file)

            # Generate PDF name from relative path
            relative_dir = os.path.relpath(root, source_root)
            pdf_name = "root.pdf" if relative_dir == '.' else relative_dir.replace(os.sep, "_") + ".pdf"
            pdf_path = os.path.join(dest_folder, pdf_name)

            print(f"Converting '{html_path}' to '{pdf_path}'")
            try:
                # Load and parse HTML
                with open(html_path, 'r') as f:
                    soup = BeautifulSoup(f.read(), "html.parser")

                # Add print-specific CSS to suppress background and color red suits
                style_tag = soup.new_tag("style", media="print")
                
                style_tag.string = """
                    * {
                        background: none !important;
                        background-color: transparent !important;
                    }
					h3 {
						color: #0000cc;
					}
                    .red-suit {
                        color: red !important;
                    }
					table {
						border-collapse: collapse;
						border: 2px solid #0000cc;
					}
					table td, table th {
						border: 1px solid #0000cc;
						background-color: #ccccff;
						padding: 5px;
					}
                """
                soup.head.append(style_tag)

                # Apply red styling to ♥ and ♦ symbols
                style_suit_symbols(soup)

                # Render to PDF using modified HTML
                HTML(string=str(soup), base_url=root).write_pdf(pdf_path)
                print(f"Successfully created '{pdf_path}'")

            except Exception as e:
                print(f"Error converting '{html_path}': {e}")