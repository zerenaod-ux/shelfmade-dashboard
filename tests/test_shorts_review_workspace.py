from html.parser import HTMLParser
from pathlib import Path
import unittest


PAGE = Path(__file__).resolve().parents[1] / "index.html"


class ShelfMadeShortsWorkspaceTests(unittest.TestCase):
    def test_shorts_are_separate_and_review_and_publish_share_one_view(self):
        html = PAGE.read_text()
        self.assertIn('data-view="shorts"', html)
        self.assertIn('id="view-shorts"', html)
        self.assertIn('id="short-review-cards"', html)
        self.assertIn('id="chatpublish"', html)
        self.assertNotIn('data-view="ready"', html)
        self.assertNotIn('id="view-ready"', html)
        self.assertIn("changeView('shorts')", html)

    def test_existing_owner_review_and_confirmed_publish_gates_remain(self):
        html = PAGE.read_text()
        self.assertIn("if(needsApproval)await api('/api/decision',{id:i.id,status:'approved',checks})", html)
        self.assertIn("api('/api/publishing/prepare',{id:i.id,title:title.value,description:description.value})", html)
        self.assertIn("api('/api/multiplatform/publish',{id:prep.id,platforms:selectedPlatforms(),confirm:true})", html)
        self.assertIn("review=items.filter(i=>i.status==='review'&&!done(i))", html)

    def test_page_has_unique_element_ids(self):
        class IdCollector(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = []

            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if "id" in values:
                    self.ids.append(values["id"])

        parser = IdCollector()
        parser.feed(PAGE.read_text())
        duplicates = {value for value in parser.ids if parser.ids.count(value) > 1}
        self.assertFalse(duplicates, f"duplicate element IDs: {sorted(duplicates)}")


if __name__ == "__main__":
    unittest.main()
