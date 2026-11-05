import unittest
from footage_credit_copy import strip_optional_pexels
import captions,footage_director
class OptionalCredits(unittest.TestCase):
 def test_pexels_list_removed_but_book_and_music_sources_remain(self):
  text='A useful lesson.\n\nSource: https://www.gutenberg.org/ebooks/2274\n\nVideos provided by Pexels — https://www.pexels.com\nTima — https://www.pexels.com/video/clock-8322008/\nhttps://kaboompics.com/ — https://www.pexels.com/video/calendar-8134590/\n\nMusic: Artist — https://example.com/license\n#books'
  result=strip_optional_pexels(text)
  self.assertNotIn('pexels.com',result);self.assertIn('gutenberg.org',result);self.assertIn('Music: Artist',result);self.assertIn('#books',result)
 def test_creator_link_outside_block_is_not_silently_removed(self):
  text='A reader requested this source: https://www.pexels.com/video/clock-8322008/'
  self.assertEqual(strip_optional_pexels(text),text)
 def test_other_required_credit_is_preserved(self):
  text='Licensed footage: Other artist — https://example.com/clip\nLicense: CC BY 4.0\nAttribution required.'
  self.assertEqual(strip_optional_pexels(text),text)
 def test_public_caption_pipeline_and_future_generation_are_clean(self):
  text='CAPTION (paste in description):\nA useful lesson.\n\nVideos provided by Pexels — https://www.pexels.com\nArtist — https://www.pexels.com/video/test-1/'
  self.assertEqual(captions.clean(text),'A useful lesson.')
  self.assertEqual(footage_director.credit_block([{'creator':'Artist','source_url':'https://www.pexels.com/video/test-1/'}]),'')
 def test_following_public_paragraph_survives_and_cleaning_is_idempotent(self):
  text='Opening.\nVideos provided by Pexels — https://www.pexels.com\nArtist — https://www.pexels.com/video/test-1/\n\nFollow ShelfMade for more.'
  result=strip_optional_pexels(text);self.assertIn('Follow ShelfMade',result);self.assertEqual(strip_optional_pexels(result),result)
