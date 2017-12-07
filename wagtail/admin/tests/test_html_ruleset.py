from django.test import TestCase

from wagtail.admin.rich_text.converters.html_ruleset import HTMLRuleset


class TestHTMLRuleset(TestCase):
    def test_html_ruleset(self):
        ruleset = HTMLRuleset({
            'p': 'paragraph',
            'a[href]': 'link',
            'a[linktype="page"]': 'page-link',
        })

        self.assertEqual(ruleset.match('div', {}), None)
        self.assertEqual(ruleset.match('p', {}), 'paragraph')
        self.assertEqual(ruleset.match('p', {'class': 'intro'}), 'paragraph')
        self.assertEqual(ruleset.match('a', {'class': 'button'}), None)
        self.assertEqual(ruleset.match('a', {'class': 'button', 'href': 'http://wagtail.io'}), 'link')
        self.assertEqual(ruleset.match('a', {'class': 'button', 'linktype': 'document'}), None)
        self.assertEqual(ruleset.match('a', {'class': 'button', 'linktype': 'page'}), 'page-link')
