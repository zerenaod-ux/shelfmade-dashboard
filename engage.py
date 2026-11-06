"""Comment prompt for Short captions (2026-11-05): zero comments on all channels, so every Short ends with one easy question to answer."""
import hashlib
POOL = {
 'shelfmade': ['Which line would you keep? Tell me below.', 'Have you read this book? Tell me in the comments.', 'Does this still hold true today? Tell me below.',
               'Which book changed you? Name it in the comments.', 'Agree or disagree? One word below.'],
 'mindlore': ['Has this ever happened to you? Tell me in the comments.', 'Which part felt most true? Tell me below.', 'Do you do this too? Be honest in the comments.',
              'What should we explain next? Tell me below.', 'Agree or disagree? One word below.'],
 'doodles': ['Are you Leo or Mia today? Tell me below.', 'Which one of them is you? Comment below.', 'What should Leo and Mia fight about next? Tell me below.',
             'Has this happened to you? Tell me below.'],
}
def add(text, brand, title=''):
    pool = POOL.get(brand)
    if not pool or not text:
        return text
    if any(q in text for p in POOL.values() for q in p):
        return text
    q = pool[int(hashlib.sha1((title or text).encode()).hexdigest(), 16) % len(pool)]
    return text.rstrip() + '\n\n' + q
