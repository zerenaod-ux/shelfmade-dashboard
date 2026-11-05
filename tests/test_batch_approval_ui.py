import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BatchApprovalUiTests(unittest.TestCase):
    def test_video_cards_expose_stable_ids_for_batch_selection(self):
        html = (ROOT / 'index.html').read_text()
        script = (ROOT / 'batch-approval.js').read_text()
        server = (ROOT / 'server.py').read_text()

        self.assertIn('b.dataset.itemId=i.id', html)
        self.assertIn('const itemId = card.dataset.itemId;', script)
        self.assertNotIn('card.onclick?.toString()', script)
        self.assertIn('<script src="batch-approval.js"></script>', html)
        self.assertIn("if path=='/batch-approval.js':", server)
        self.assertIn("(BASE/'batch-approval.js').read_bytes()", server)
        self.assertIn('Confirm you reviewed the facts, narration, and visuals', script)


if __name__ == '__main__':
    unittest.main()
