from bs4 import BeautifulSoup


def extract_final_auction(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all tables
    tables = soup.find_all('table')

    # Filter tables that contain the auction (WEST NORTH EAST SOUTH row)
    auction_tables = [
        table for table in tables
        if any("WEST" in cell.get_text(strip=True) for cell in table.find_all("td")) and
           any("NORTH" in cell.get_text(strip=True) for cell in table.find_all("td"))
    ]
    
    if not auction_tables:
        return None

    # Select the last auction table
    final_auction_table = auction_tables[-1]

    # Extract rows with bids
    rows = final_auction_table.find_all('tr')[1:]  # Skip the header row

    auction_data = []
    for row in rows:
        cells = row.find_all('td', {'align': 'center'})
        if cells:
            auction_data.append([cell.get_text(strip=True) for cell in cells])

    # Filter out empty rows
    auction_data = [row for row in auction_data if any(row)]

    return auction_data


# Example usage
if __name__ == "__main__":
    with open("deal01.html", encoding="utf-8") as file:
        html_content = file.read()

    auction = extract_final_auction(html_content)
    for row in auction:
        print(row)
