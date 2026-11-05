import sys,unittest,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import captions,publishing,multiplatform
class CaptionTests(unittest.TestCase):
 def test_instruction_package(self):
  raw='READY TO POST — ShelfMade\nPlatforms: TikTok, YouTube\n══════\nYOUTUBE / TIKTOK TITLE (copy this):\nTitle\n══════\n\nCAPTION (paste in description):\n\nReal caption.\n\n📚 Book by \n\n#books\n══════\nUpload final.mp4, paste caption.'
  self.assertEqual(captions.clean(raw),'Real caption.\n\n📚 Book\n\n#books')
 def test_dash_format_and_plain_caption(self):
  self.assertEqual(captions.clean('READY TO POST — ShelfMade\n--- CAPTION ---\nHello.\n#books\nUpload final.mp4'),'Hello.\n#books')
  plain='A useful lesson.\n\nSource: https://example.com\n• One idea\n#books'
  self.assertEqual(captions.clean(plain),plain)
 def test_publication_boundary(self):
  p=multiplatform.payload('youtube','Title','CAPTION (paste in description):\nPublic words\n======','https://example.test/video.mp4')
  self.assertEqual(p['text'],'Public words')
if __name__=='__main__':unittest.main()
