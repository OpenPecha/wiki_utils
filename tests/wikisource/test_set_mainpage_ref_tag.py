import unittest

from wiki_utils.wikisource.set_mainpage_ref_tag import replace_braces_with_ref_tag


class TestReplaceBracesWithRefTag(unittest.TestCase):
    def test_tibetan(self):
        text = "ཡིག (དཔེ་ཆ།,ཤོག་ངོས།) རེད།"
        expected = "ཡིག ཤོག་ངོས།<ref>བྲིས་མར། དཔེ་ཆ།</ref> རེད།"
        self.assertEqual(replace_braces_with_ref_tag(text), expected)

    def test_no_match(self):
        text = "No pattern here."
        self.assertEqual(replace_braces_with_ref_tag(text), text)

    def test_spaces(self):
        text = "Test ( foo , bar )."
        expected = "Test bar<ref>བྲིས་མར། foo</ref>."
        self.assertEqual(replace_braces_with_ref_tag(text), expected)


if __name__ == "__main__":
    unittest.main()
