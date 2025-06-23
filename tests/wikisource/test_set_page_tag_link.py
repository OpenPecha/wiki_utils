import unittest
from unittest.mock import MagicMock, patch

from wiki_utils.wikisource.set_page_tag_link import update_mainspace_page_with_links


class TestUpdateMainspacePageWithLinks(unittest.TestCase):
    def setUp(self):
        self.index_title = "TestBook.pdf"
        self.index_title_no_ext = "TestBook"
        self.mainpage_title = "MainPageTitle"

    @patch("pywikibot.Page")
    def test_page_does_not_exist(self, mock_page):
        # Simulate page does not exist
        mock_page.return_value.exists.return_value = False
        update_mainspace_page_with_links(
            self.index_title, self.mainpage_title, dry_run=True
        )
        mock_page.return_value.text = ""  # Should not matter

        mock_page.return_value.save.assert_not_called()

    @patch("pywikibot.Page")
    def test_no_replacement_needed(self, mock_page):
        mock_page_instance = MagicMock()
        mock_page_instance.exists.return_value = True
        mock_page_instance.text = "This is a page without any page number."
        mock_page.return_value = mock_page_instance

        update_mainspace_page_with_links(
            self.index_title, self.mainpage_title, dry_run=True
        )

        mock_page_instance.save.assert_not_called()

    @patch("pywikibot.Page")
    def test_replacement_and_save(self, mock_page):
        mock_page_instance = MagicMock()
        mock_page_instance.exists.return_value = True
        mock_page_instance.text = "Introduction\nPage no: 7\nConclusion"

        mock_page.return_value = mock_page_instance

        update_mainspace_page_with_links(
            self.index_title, self.mainpage_title, dry_run=False
        )

        expected_text = "Introduction\n[[Page:TestBook.pdf/7|Page no: 7]]\nConclusion"

        # Check that the replacement happened correctly
        args, kwargs = mock_page_instance.save.call_args
        self.assertIn("Bot: Converted", kwargs["summary"])

        # Check that the text was updated
        self.assertEqual(mock_page_instance.text, expected_text)


class TestSplitByPageBlocks(unittest.TestCase):
    def test_multiple_page_blocks(self):
        from wiki_utils.wikisource.set_page_tag_link import split_by_page_blocks

        text = (
            "[[Page:TestBook.pdf/1|Page no: 1]]Content of page 1."
            "[[Page:TestBook.pdf/2|Page no: 2]]Content of page 2."
            "[[Page:TestBook.pdf/3|Page no: 3]]Content of page 3."
        )
        blocks = split_by_page_blocks(text)
        self.assertEqual(len(blocks), 3)
        self.assertTrue(blocks[0].startswith("[[Page:TestBook.pdf/1|Page no: 1]]"))
        self.assertTrue(blocks[1].startswith("[[Page:TestBook.pdf/2|Page no: 2]]"))
        self.assertTrue(blocks[2].startswith("[[Page:TestBook.pdf/3|Page no: 3]]"))


class TestExtractPageNumbers(unittest.TestCase):
    def test_extract_from_blocks(self):
        from wiki_utils.wikisource.set_page_tag_link import extract_page_numbers

        blocks = [
            "[[Page:TestBook.pdf/1|Page no: 1]]Content of page 1.",
            "[[Page:TestBook.pdf/2|Page no: 2]]Content of page 2.",
            "[[Page:TestBook.pdf/3|Page no: 3]]Content of page 3.",
        ]
        nums = extract_page_numbers(blocks)
        self.assertEqual(nums, [1, 2, 3])

    def test_no_page_numbers(self):
        from wiki_utils.wikisource.set_page_tag_link import extract_page_numbers

        blocks = ["No page number here.", "Still nothing."]
        nums = extract_page_numbers(blocks)
        self.assertEqual(nums, [])


if __name__ == "__main__":
    unittest.main()
