import csv
import logging
import re
from urllib.parse import unquote

import pywikibot
from google.oauth2 import service_account
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAFE_PAGE_SIZE = int(2 * 1024 * 1024 * 0.9)  # 1.9MB safety buffer

# ------------------ Helper functions for the oversize contents ------------------


def split_by_page_blocks(text):
    matches = list(
        re.finditer(
            r"(\[\[Page:[^\|\]]+\|Page(?:\s*no:)?\s*\d+\]\])", text, re.IGNORECASE
        )
    )

    if not matches:
        return [text]

    blocks = []
    for i in range(len(matches)):
        start = matches[i].start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        blocks.append(block)

    return blocks


def extract_page_numbers(blocks):
    """
    Extract numeric page numbers from a list of blocks like "Page no: 3"
    """
    nums = []
    for block in blocks:
        match = re.search(r"Page(?:\s*no:)?\s*(\d+)", block, re.IGNORECASE)
        if match:
            nums.append(int(match.group(1)))
    return nums


def split_and_save_subpages(mainpage_title, blocks, site, dry_run=False):
    parts = []
    current = []

    for block in blocks:
        current.append(block)
        if len("".join(current).encode("utf-8")) > SAFE_PAGE_SIZE:
            current.pop()
            parts.append(current)
            current = [block]

    if current:
        parts.append(current)

    subpages = []
    for i, part in enumerate(parts, 1):
        subpage_title = f"{mainpage_title}/{i}"
        subpage_text = "".join(part)

        # 🔍 Extract and log page range info
        page_numbers = extract_page_numbers(part)
        if page_numbers:
            start_page = min(page_numbers)
            end_page = max(page_numbers)
            print(
                f"Subpage {i}: {subpage_title} contains Page no: {start_page} to {end_page}"
            )
        else:
            print(f"Subpage {i}: {subpage_title} contains unknown page numbers")

        if dry_run:
            print(
                f"---------------\n\n[DRY RUN] Would save subpage: {subpage_title} ------------\n\n"
            )
            print(subpage_text[:300])
        else:
            subpage = pywikibot.Page(site, subpage_title)
            subpage.text = subpage_text
            try:
                subpage.save(summary="Bot: Split large main page content")
                subpages.append(subpage_title)
            except Exception as e:
                print(f"Error saving subpage {subpage_title}: {e}")
                return None
    return subpages


def update_mainspace_page_with_links(
    index_title: str,
    mainpage_title: str,
    site_code="mul",
    family="wikisource",
    dry_run=False,
):
    """
    Replace 'Page no: N' in a mainspace page with links to the corresponding Page:Index/N.
    """
    site = pywikibot.Site(site_code, family)
    page = pywikibot.Page(site, mainpage_title)

    if not page.exists():
        logger.info(f"Main page '{mainpage_title}' does not exist.")
        return

    original_text = page.text

    # 🔍 Check if it's already converted
    link_pattern = re.compile(
        r"\[\[Page:[^/\|\]]+/\d+\|Page(?:\s*no:)?\s*\d+\]\]", re.IGNORECASE
    )
    if link_pattern.search(original_text):
        logger.info(
            f"Page '{mainpage_title}' already contains page links in final format. Skipping..."
        )
        return

    def link_replacer(match):
        num = match.group(1)
        return f"[[Page:{index_title}/{num}|Page no: {num}]]"

    updated_text = re.sub(
        r"Page(?:\s*no:)?\s*(\d+)", link_replacer, original_text, flags=re.IGNORECASE
    )

    if original_text == updated_text:
        logger.info("No changes needed.")
        return

    # 📝 Try saving directly first
    page.text = updated_text

    try:
        page.save(summary="Bot: Converted 'Page no:' references to page links.")
        logger.info(f"✅ Successfully updated main page: {mainpage_title}")
    except Exception as e:
        logger.error(f"\n\n⚠️ Initial save failed: {e}\n\n")
        logger.info("\n\n📦 Attempting to split content into subpages...\n\n")

        # 🔀 Split and save subpages if main page is too large
        blocks = split_by_page_blocks(updated_text)
        subpages = split_and_save_subpages(mainpage_title, blocks, site, dry_run=False)

        if subpages:
            transclusion_text = "\n\n".join(
                f"{{{{:{title}}}}}" for title in subpages  # noqa: E231
            )
            page.text = transclusion_text

            if dry_run:
                print(
                    "\n\n------------🔍 [DRY RUN] Would save main page with subpage transclusions:-------\n\n"
                )
                print(transclusion_text[:2000])
                return
            try:
                page.save(
                    summary="Bot: Split oversized main page and added subpage transclusions."
                )
                logger.info("✅ Main page split and saved with transclusions.")
            except Exception as final_err:
                logger.error(
                    f"\n\n❌ Final save failed after splitting: {final_err}\n\n"
                )


def get_wikisource_links(
    sheet_id,
    creds_path,
    range_rows,
    output_file="wikisource_links.csv",
):
    """
    Extracts hyperlinks from 'Text File link' (G) and 'Wikisource Link' (H) columns
    only if BOTH are present and 'Proofreading statue' (J) == 'ཞུ་དག་བྱས་ཟིན།'.
    You can change the value of range_rows to get more or less rows.
    Doing this because of some links are set up differently. not in uniform order.

    Args:
        sheet_id (str): Google Sheet ID
        creds_path (str): Path to service account JSON credentials
        range_rows (str): Range including G, H, J columns
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
        spreadsheetId=sheet_id, ranges=[range_rows], includeGridData=True
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
    Check for if index_title_no_ext equals with mainpage_title. if same then skip the link.

    index_title = "སྙན་བརྒྱུད་ཁྲིད་ཆེན་བཅུ་གསུམ་གྱི་སྐོར། པོད། ༡.pdf"
    index_title_no_ext = "སྙན་བརྒྱུད་ཁྲིད་ཆེན་བཅུ་གསུམ་གྱི་སྐོར། པོད། ༡"
    mainpage_title = (
        "རྒྱལ་བ་ཀཿཐོག་པའི་གྲུབ་མཆོག་རྣམས་ཀྱི་ཉམས་བཞེས་ཁྲིད་ཆེན་བཅུ་གསུམ་གྱི་པོད་དང་པོ།"
    )
    range_rows = it is basically the range that you want from googlesheet.
    """

    SPREADSHEET_ID = "1vtQ_aCDN1Y9jbwmJEE48aIgPauRvheFgYF6X1xKieMo"
    CREDS_PATH = "my-credentials.json"
    range_rows = "ཡིག་བརྒྱའི་ལས་གཞི།!G6:J6"

    valid_pairs = get_wikisource_links(SPREADSHEET_ID, CREDS_PATH, range_rows)

    for ws_link, txt_link in valid_pairs:
        index_title = unquote(ws_link.split("Index:")[-1])
        mainpage_title = unquote(txt_link.split("/wiki/")[-1])
        # NEW: Extract only the text before '.pdf'
        index_text = index_title.rsplit(".pdf", 1)[0]

        if index_text == mainpage_title:
            logger.info(
                f"Skipping index: {index_title} and mainpage: {mainpage_title} because they are the same."
            )
            continue

        logger.info(f"Processing index: {index_title}")
        logger.info(f"Index text: {index_text}")
        logger.info(f"Mainpage title: {mainpage_title}")
        print("\n\n")

        update_mainspace_page_with_links(index_title, mainpage_title, dry_run=False)
        print("\n\n----------- ONTO NEXT ONE ------------\n\n")

    print("✅ All processes completed.")
