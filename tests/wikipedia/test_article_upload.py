import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from wiki_utils.wikipedia.article_upload import (
    create_article,
    edit_article,
    get_article,
    login_to_wikipedia,
)


class TestArticleUpload(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        # Create mock site without spec to avoid attribute errors
        self.mock_site = MagicMock()
        self.mock_site.username.return_value = "TestUser"

        # Create mock page without spec to avoid attribute errors
        self.mock_page = MagicMock()
        self.mock_page.text = "Original page content"

    @patch("pywikibot.Site")
    @patch("wiki_utils.wikipedia.article_upload.logger")
    def test_login_to_wikipedia(self, mock_logger, mock_site_class):
        """Test login to Wikipedia function"""
        # Configure the mock
        mock_site_instance = mock_site_class.return_value
        mock_site_instance.username.return_value = "TestUser"

        # Call the function
        result = login_to_wikipedia("en")

        # Verify the mock was called correctly
        mock_site_class.assert_called_once_with("en", "wikipedia")
        mock_site_instance.login.assert_called_once()
        mock_logger.info.assert_called_once()

        # Assert the result is the mocked site
        self.assertEqual(result, mock_site_instance)

    def test_get_article(self):
        """Test getting an article by title"""
        # Configure the mock
        with patch("pywikibot.Page") as mock_page_class:
            mock_page_instance = mock_page_class.return_value

            # Call the function
            result = get_article(self.mock_site, "Test Article")

            # Verify the mock was called correctly
            mock_page_class.assert_called_once_with(self.mock_site, "Test Article")

            # Assert the result is the mocked page
            self.assertEqual(result, mock_page_instance)

    @patch("pywikibot.Page")
    @patch("wiki_utils.wikipedia.article_upload.logger")
    def test_create_article_already_exists(self, mock_logger, mock_page_class):
        """Test creating an article that already exists"""
        # Configure the mock
        mock_page_instance = mock_page_class.return_value
        mock_page_instance.text = "Original content"
        mock_page_instance.exists.return_value = True

        # Call the function
        result = create_article(self.mock_site, "Test Article", "New content")

        # Verify behavior
        self.assertFalse(result)  # Should return False
        mock_page_class.assert_called_once_with(self.mock_site, "Test Article")
        mock_page_instance.exists.assert_called_once()
        mock_logger.warning.assert_called_once()
        self.assertNotEqual(
            mock_page_instance.text, "New content"
        )  # Content should not be changed

    @patch("pywikibot.Page")
    @patch("wiki_utils.wikipedia.article_upload.logger")
    def test_create_article_new(self, mock_logger, mock_page_class):
        """Test creating a new article"""
        # Configure the mock
        mock_page_instance = mock_page_class.return_value
        mock_page_instance.text = ""
        mock_page_instance.exists.return_value = False

        # Call the function
        result = create_article(
            self.mock_site,
            "New Article",
            "Article content",
            summary="Created via test",
            minor=True,
        )

        # Verify behavior
        self.assertTrue(result)  # Should return True
        mock_page_class.assert_called_once_with(self.mock_site, "New Article")
        self.assertEqual(
            mock_page_instance.text, "Article content"
        )  # Content should be updated
        mock_page_instance.save.assert_called_once_with(
            summary="Created via test", minor=True
        )
        mock_logger.info.assert_called_once()

    @patch("pywikibot.Page")
    @patch("builtins.open", new_callable=mock_open)
    @patch("wiki_utils.wikipedia.article_upload.logger")
    def test_edit_article_existing(self, mock_logger, mock_file, mock_page_class):
        """Test editing an existing article"""
        # Configure the mock
        mock_page_instance = mock_page_class.return_value
        mock_page_instance.text = "Original content"
        mock_page_instance.exists.return_value = True

        # Call the function
        result = edit_article(
            self.mock_site,
            "Existing Article",
            "Updated content",
            summary="Updated via test",
            minor=False,
        )

        # Verify behavior
        self.assertTrue(result)  # Should return True
        mock_page_class.assert_called_once_with(self.mock_site, "Existing Article")
        self.assertEqual(
            mock_page_instance.text, "Updated content"
        )  # Content should be updated
        mock_page_instance.save.assert_called_once_with(
            summary="Updated via test", minor=False
        )
        mock_file.assert_called_once_with("article_content.txt", "w")
        # Verify logger calls
        self.assertEqual(
            mock_logger.info.call_count, 2
        )  # Two info calls (content and success)
        # Clean up
        Path("article_content.txt").unlink()

    @patch("pywikibot.Page")
    @patch("wiki_utils.wikipedia.article_upload.logger")
    def test_create_article_exception(self, mock_logger, mock_page_class):
        """Test exception handling in create_article"""
        # Configure the mock to raise an exception
        mock_page_instance = mock_page_class.return_value
        mock_page_instance.exists.side_effect = Exception("Test exception")

        # Call the function
        result = create_article(self.mock_site, "Problem Article", "Content")

        # Verify behavior
        self.assertFalse(result)  # Should return False on exception
        mock_logger.error.assert_called_once()

    @patch("pywikibot.Page")
    @patch("wiki_utils.wikipedia.article_upload.logger")
    def test_edit_article_nonexistent(self, mock_logger, mock_page_class):
        """Test editing a non-existent article"""
        # Configure the mock
        mock_page_instance = mock_page_class.return_value
        mock_page_instance.exists.return_value = False

        # Call the function
        result = edit_article(self.mock_site, "Non-existent Article", "Content")

        # Verify behavior
        self.assertFalse(result)  # Should return False
        mock_logger.warning.assert_called_once()
        mock_page_instance.save.assert_not_called()

    @patch("pywikibot.Page")
    @patch("wiki_utils.wikipedia.article_upload.logger")
    def test_edit_article_exception(self, mock_logger, mock_page_class):
        """Test exception handling in edit_article"""
        # Configure the mock to raise an exception
        mock_page_instance = mock_page_class.return_value
        mock_page_instance.exists.return_value = True
        mock_page_instance.save.side_effect = Exception("Test exception")

        # Call the function
        result = edit_article(self.mock_site, "Problem Article", "Content")

        # Verify behavior
        self.assertFalse(result)  # Should return False on exception
        mock_logger.error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
