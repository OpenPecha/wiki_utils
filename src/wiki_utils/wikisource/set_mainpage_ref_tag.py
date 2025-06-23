import csv
import re
from urllib.parse import unquote

import pywikibot
from google.oauth2 import service_account
from googleapiclient.discovery import build


def replace_braces_with_ref_tag(text):
    """
    Replaces (word1,word2) with word2<ref>word1</ref> in the text.
    Handles Tibetan and standard punctuation/spacing.
    """

    # Pattern: (word1,word2) with optional spaces and Tibetan punctuation
    pattern = r"\(([^,\)]+),([^\)]+)\)"

    def replacer(match):
        word1 = match.group(1).strip()
        word2 = match.group(2).strip()
        return f"{word2}<ref>བྲིས་མར། {word1}</ref>"

    return re.sub(pattern, replacer, text)


def update_mainspace_page_with_ref_tag(
    mainpage_title: str,
    site_code="mul",
    family="wikisource",
    dry_run=True,
    save_to_files=False,
):
    """
    Replace 'Page no: N' in a mainspace page with links to the corresponding Page:Index/N.

    Args:
        mainpage_title: Title of the mainspace page
        site_code: Site code for pywikibot
        family: Family for pywikibot
        dry_run: If True, only preview changes without saving
        save_to_files: If True, save original and updated text to files
    """
    site = pywikibot.Site(site_code, family)
    page = pywikibot.Page(site, mainpage_title)

    if not page.exists():
        print(f"Main page '{mainpage_title}' does not exist.")
        return

    original_text = page.text
    updated_text = replace_braces_with_ref_tag(original_text)

    if original_text == updated_text:
        print("No changes needed.")
        return

    # Save texts to files if requested
    if save_to_files:
        # Create safe filename from title
        safe_title = mainpage_title.replace("/", "_").replace("\\", "_")[
            :50
        ]  # Limit length and replace slashes

        # Save original text
        with open(f"{safe_title}_original.txt", "w", encoding="utf-8") as f:
            f.write(original_text)
        print(f"Original text saved to {safe_title}_original.txt")

        # Save updated text
        with open(f"{safe_title}_updated.txt", "w", encoding="utf-8") as f:
            f.write(updated_text)
        print(f"Updated text saved to {safe_title}_updated.txt")

    if dry_run:
        print("Dry run only — not saving changes.")
        print(updated_text[:2000])  # Preview first 2000 characters
    else:
        try:
            page.text = updated_text
            page.save(summary="Bot: Converted 'Page no:' references to page links.")
        except Exception as e:
            print(f"\n\n ❌❌❌Failed to save page '{page.title()}': {e} ❌❌❌\n\n")
            return


def get_wikisource_links(
    sheet_id,
    creds_path,
    range_GSheet,
    output_file="wikisource_links.csv",
):
    """
    Extracts hyperlinks from 'Text File link' (G) and 'Wikisource Link' (H) columns
    only if BOTH are present and 'Proofreading statue' (J) == 'ཞུ་དག་བྱས་ཟིན།'.
    You can change the value of range to get more or less rows.
    Doing this because of some links are set up differently. not in uniform order.

    Args:
        sheet_id (str): Google Sheet ID
        creds_path (str): Path to service account JSON credentials
        range (str): Range including G, H, J columns
        output_file (str): Where to save the extracted URLs

    Returns:
        List of tuples: [(wikisource_link, text_file_link), ...]
    """

    target_status = "ཞུ་དག་བྱས་ཟིན།"

    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    result = sheet.get(
        spreadsheetId=sheet_id, ranges=[range_GSheet], includeGridData=True
    ).execute()

    rows = result["sheets"][0]["data"][0]["rowData"]
    links = []

    for row in rows:
        try:
            values = row["values"]
            text_file_cell = values[0]  # Column G
            wikisource_cell = values[1]  # Column H
            status_cell = values[3].get("formattedValue", "")  # Column J

            if (
                status_cell.strip() == target_status
                and "hyperlink" in text_file_cell
                and "hyperlink" in wikisource_cell
            ):
                text_file_link = text_file_cell["hyperlink"]
                wikisource_link = wikisource_cell["hyperlink"]
                links.append((wikisource_link, text_file_link))

        except (KeyError, IndexError):
            continue

    # Save to CSV. so that you can understand the output. Not much of a use in code logic
    with open(output_file, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Wikisource Link", "Text File Link"])
        for ws_link, txt_link in links:
            writer.writerow([ws_link, txt_link])

    print(f"✅ {len(links)} valid link pairs saved to '{output_file}'.")

    return links


if __name__ == "__main__":
    """
    The googlesheet links extracted comes in both wikisource_link and textfile_link. Choose accordingly.

    mainpage_title = "རྒྱལ་བ་ཀཿཐོག་པའི་གྲུབ་མཆོག་རྣམས་ཀྱི་ཉམས་བཞེས་ཁྲིད་ཆེན་བཅུ་གསུམ་གྱི་པོད་དང་པོ།"
    """

    SPREADSHEET_ID = "1jDZMBuGKGc9x3SXuwVo3ix60fDUccXgHPsAgFmUNCIw"
    CREDS_PATH = "my-credentials.json"
    range_GSheet = "ལས་ཀ་དངོས་གཞི།!G38:J48"

    valid_pairs = get_wikisource_links(SPREADSHEET_ID, CREDS_PATH, range_GSheet)

    for ws_link, txt_link in valid_pairs:
        mainpage_title = unquote(txt_link.split("/wiki/")[-1])
        print(f"\n\n👍🏻👍🏻👍🏻{mainpage_title}👍🏻👍🏻👍🏻\n\n")
        update_mainspace_page_with_ref_tag(
            mainpage_title, dry_run=False, save_to_files=False
        )
        print("\n\n----------- ONTO NEXT ONE ------------\n\n")

    print("✅ All processes completed.")
