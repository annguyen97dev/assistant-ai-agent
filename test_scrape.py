import unittest

from scrape import html_to_markdown, slugify


class MarkdownConversionTests(unittest.TestCase):
    def test_preserves_content_and_relative_links(self):
        source = (
            '<nav>Site menu</nav>'
            '<h2>Setup</h2>'
            '<p>See <a href="../next-step">next step</a>.</p>'
            '<pre><code>print("hello")\n</code></pre>'
        )
        result = html_to_markdown(source)
        self.assertIn("## Setup", result)
        self.assertIn("[next step](../next-step)", result)
        self.assertIn('```\nprint("hello")\n```', result)
        self.assertNotIn("Site menu", result)

    def test_removes_article_navigation_and_support_boilerplate(self):
        source = (
            '<h3>In this article:</h3><ul><li><a href="#setup">Setup</a></li></ul>'
            '<h2 id="setup">Setup</h2><p>Useful instruction.</p>'
            '<p>If you have any additional questions, email '
            '<a href="mailto:support@optisigns.com">support@optisigns.com</a>.</p>'
        )
        result = html_to_markdown(source)
        self.assertIn("## Setup", result)
        self.assertIn("Useful instruction", result)
        self.assertNotIn("In this article", result)
        self.assertNotIn("#setup", result)
        self.assertNotIn("additional questions", result)

    def test_slug_is_stable(self):
        self.assertEqual(slugify("How to Use YouTube with OptiSigns"), "how-to-use-youtube-with-optisigns")


if __name__ == "__main__":
    unittest.main()
