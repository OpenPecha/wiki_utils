import csv
import logging
import re
from urllib.parse import unquote

import pywikibot
from google.oauth2 import service_account
from googleapiclient.discovery import build

# from wiki_utils.utils.logger import get_logger


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def get_logger(name):
    return logging.getLogger(name)


# Initialize the logger
logger = get_logger(__name__)


def extract_page_number(page):
    # Extracts the number after the last '/' in the title, returns as int if possible
    m = re.search(r"/(\d+)$", page.title())
    return int(m.group(1)) if m else float("inf")


def get_base_info(site, index_title):
    """
    Extract base title components and namespace information from an Index title

    :param site: pywikibot.Site object
    :param index_title: Title of the Index page, e.g., "Index:SomeBook.pdf"
    :return: Tuple of (base_title, base_title_no_ext, index_ns, page_ns, page_prefix)
    """
    # Get the base name for constructing page titles
    if index_title.startswith("Index:"):
        index_prefix_len = len("Index:")
        base_title = index_title[index_prefix_len:]
    else:
        base_title = index_title

    if "." in base_title:
        base_title_no_ext = ".".join(base_title.split(".")[:-1])
    else:
        base_title_no_ext = base_title

    # Get namespace IDs
    index_ns = site.namespace(106)  # Index namespace
    page_ns = site.namespace(104)  # Page namespace

    # Generate query for pages in Page namespace that belong to this index
    page_prefix = f"{page_ns}:{base_title_no_ext}/"  # noqa

    return base_title, base_title_no_ext, index_ns, page_ns, page_prefix


def get_pages(site, index_title):
    """
    Get all Page: namespace pages associated with an Index
    :param site: pywikibot.Site object
    :param index_title: Title of the Index page, e.g., "Index:SomeBook.pdf"
    :return: List of pywikibot.Page objects sorted by page number
    """
    # Get base info using the new function
    _, base_title_no_ext, _, _, page_prefix = get_base_info(site, index_title)

    logger.info(f"Looking for pages with prefix: {page_prefix}")

    # Get all pages that belong to this index
    pages = list(site.allpages(prefix=base_title_no_ext, namespace=104))

    # Sort pages by page number
    pages = sorted(pages, key=extract_page_number)

    if not pages:
        logger.warning(f"No pages found for index: {index_title}")
    else:
        logger.info(f"Found {len(pages)} pages to process")

    return pages


def format_page_orientation(index_title, site=None, dry_run=False):
    """
    Create a mainspace page for a given Index page by transcluding its text.
    Also, wrap each page in the Index with a styled div if it exists.
    :param index_title: Title of the Index page, e.g., "Index:SomeBook.pdf"
    :param site: pywikibot.Site object for bo.wikisource
    :param dry_run: If True, do not actually save the page
    """

    if site is None:
        site = pywikibot.Site("mul", "wikisource")

    # added this part of code so to check if the main page already exists then no need to modify the pages again.
    # NOTICE: If you still want to make changes due to some reason, you can comment out this part of code.

    _, base_title_no_ext, _, _, _ = get_base_info(site, index_title)
    main_title = base_title_no_ext
    main_page = pywikibot.Page(site, main_title)

    if main_page.exists():
        logger.info(
            f"Main page '{main_title}' already exists so no modifications of pages."
        )
        # Print a prominent, colored, bordered message for terminal visibility
        border = "\033[95m" + "\n" + "=" * 70 + "\033[0m"  # Magenta border
        message = f"\033[93m\n⚠️  Main page '{main_title}' already exists. No modifications of pages.\033[0m"
        print(border)
        print(message)
        print(border)
        print("\n")
        return

    # --- Step 1: Check if Index page exists and process each page ---
    index_page = pywikibot.Page(site, index_title)
    if not index_page.exists():
        print(f"Index page '{index_title}' does not exist!")
        return

    # Get pages using the new get_pages function
    pages = get_pages(site, index_title)

    # Process each page
    for page in pages:
        logger.info(f"Processing page: {page.title()}")
        try:
            if page.exists():
                orig_text = page.text.strip()
                # Remove any other HTML tags from the main content
                # (This preserves the actual text while removing formatting tags)
                main_text = re.sub(r"<[^>]+>", "", orig_text).strip()

                if main_text:  # Apply our styling to the clean text
                    styled_content = (
                        '<div style="margin-left: 3em; margin-right: 3em;">'
                        f"{main_text}"
                        "</div>"
                        "<noinclude></noinclude>"
                    )

                else:
                    styled_content = (
                        '<div style="margin-left: 3em; margin-right: 3em;">'
                        "&nbsp;"
                        "</div>"
                        "<noinclude></noinclude>"
                    )

                # Set proofread status to level 3 with specific user
                user = site.username()
                quality_tag = (
                    f'<noinclude><pagequality level="3" user="{user}" /></noinclude>'
                )

                logger.info(
                    f"Setting proofread status to level 3 for page: {page.title()}"
                )

                # Format text in the correct ProofreadPage format with newlines
                new_text = f"{quality_tag}\n{styled_content}"

                logger.info(f"Updating page: {page.title()}")
                if not dry_run:
                    page.text = new_text
                    # Set the proofread_page_quality property
                    page.proofread_page_quality = 3  # 3 = Proofread
                    # Use the same summary as in etext_upload.py
                    page.save(
                        summary="Bot: Adding margin styling and marking as proofread."
                    )
                else:
                    print(f"Updated text:\n{new_text[:1000]}\n")  # noqa
                    logger.info("Dry run: not saving page.")
        except Exception as e:
            logger.error(f"Error processing page {page.title()}: {e}")


def create_main_page(
    index_title, main_title=None, from_page=1, to_page=None, site=None, dry_run=False
):
    """
    Create a mainspace page for a given Index page using <pages> tag for transclusion.

    :param index_title: "Index:SomeBook.pdf"
    :param main_title: "SomeBook"
    :param from_page: (default: 1)
    :param to_page: (default: None, will use last available page)
    :param site: pywikibot.Site
    :param dry_run: If True, do not actually save the page
    :return: The created main page object
    """

    if site is None:
        site = pywikibot.Site("mul", "wikisource")

    # Check if Index page exists
    index_page = pywikibot.Page(site, index_title)
    if not index_page.exists():
        logger.error(f"Index page '{index_title}' does not exist!")
        return None

    # Use the get_base_info function to extract title components
    base_title, base_title_no_ext, _, _, _ = get_base_info(site, index_title)

    # Get pages using the get_pages function
    pages = get_pages(site, index_title)

    if not pages:
        logger.warning(f"No pages found for index: {index_title}")
        return None

    # If no main_title provided, derive it from base_title_no_ext
    if main_title is None:
        main_title = base_title_no_ext

    # If to_page not specified, use the last available page
    if to_page is None and pages:
        last_page = pages[-1]
        to_page = extract_page_number(last_page)

    # Create the actual content with <pages> tag
    # The index attribute should not include the "Index:" prefix
    content = f'<pages index="{index_title[len("Index:"):]}" from={from_page} to={to_page} />'  # noqa

    # Create or update the main page
    main_page = pywikibot.Page(site, main_title)

    if main_page.exists():
        print(f"Main page '{main_title}' already exists.")
        return

    if not dry_run:
        main_page.text = content
        main_page.save(summary="Bot: Creating mainspace transclusion of Index pages")
        logger.info(f"Mainspace page created: {main_title}")

    return


def get_wikisource_links(
    sheet_id,
    creds_path,
    range_rows,
    output_file="wikisource_links.csv",
):
    """
    Extracts hyperlinks from 'Wikisource Link' column (H) if corresponding 'Proofreading statue' column (J)
    is 'ཞུ་དག་བྱས་ཟིན།'.

    Args:
        sheet_id (str): Google Sheet ID
        creds_path (str): Path to service account JSON credentials
        range (str): Range including both H and J columns
        output_file (str): Where to save the extracted URLs

    Returns:
        List of filtered URLs
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
            link_cell = row["values"][1]  # Column H
            status_cell = row["values"][3].get("formattedValue", "")  # Column J

            if status_cell.strip() == target_status and "hyperlink" in link_cell:
                links.append(link_cell["hyperlink"])
        except (KeyError, IndexError):
            continue

    # Save to CSV
    with open(output_file, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Wikisource Link"])
        for link in links:
            writer.writerow([link])

    print(f"✅ {len(links)} links saved to '{output_file}'.")

    return links


if __name__ == "__main__":
    SPREADSHEET_ID = "1vtQ_aCDN1Y9jbwmJEE48aIgPauRvheFgYF6X1xKieMo"
    CREDS_PATH = "my-credentials.json"
    range_rows = "ལས་ཀ་དངོས་གཞི།!G48:J48"

    valid_links = get_wikisource_links(SPREADSHEET_ID, CREDS_PATH, range_rows)
    print("Links Received")

    for link in valid_links:
        if link and "/wiki/" in link:
            # Extract everything after '/wiki/' and decode URL encoding
            index_title = unquote(link.split("/wiki/")[-1])
            print(f"Processing: {index_title}")
            format_page_orientation(index_title)
            create_main_page(index_title)
            print("\n\n✅✅✅✅✅ ONTO NEXT ONE ✅✅✅✅✅\n\n")

    print("✅ All transclusions completed.")
