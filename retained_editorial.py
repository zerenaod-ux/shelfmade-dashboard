"""Verify editorial evidence against a pinned local original, without network calls."""
import json
import retained_sources

def normalize(text):return ' '.join(text.split())

def evidence(script,book):
 if str(script.get('book_id'))!=str(book):raise ValueError('Editorial script book identity mismatch.')
 original=retained_sources.read(book)
 if original is None:raise ValueError('Retain and verify this original text before admitting its editorial script.')
 entry=next(e for e in json.loads((retained_sources.ROOT/'catalogue.json').read_text()) if e['id']==str(book))
 if script.get('source_url')!=entry['canonical_url']:raise ValueError('Editorial source link does not match the retained book identity.')
 if script.get('retained_source_sha256')!=entry['sha256']:raise ValueError('Editorial evidence is pinned to a different original text.')
 sections=script.get('sections',[]);passages=script.get('source_passages',[])
 if not isinstance(sections,list) or not sections or not isinstance(passages,list) or any(not isinstance(p,dict) or type(p.get('section')) is not int or not isinstance(p.get('excerpt'),str) for p in passages):raise ValueError('Editorial chapter evidence has an invalid structure.')
 if len(passages)!=len(sections) or {p.get('section') for p in passages}!=set(range(len(sections))):raise ValueError('Each editorial chapter requires an original source passage.')
 body=normalize(original);result=[]
 for passage in sorted(passages,key=lambda p:p['section']):
  excerpt=normalize(passage.get('excerpt',''))
  if len(excerpt.split())<8 or len(excerpt)>1500 or excerpt not in body:raise ValueError('Editorial evidence passage is absent from the retained original text.')
  result.append({'section':passage['section'],'chapter':sections[passage['section']]['title'],'source_chapter':passage.get('source_chapter',''),'kind':'retained original passage','excerpt':excerpt,'source_url':entry['canonical_url'],'source_sha256':entry['sha256'],'exact_passage_verified':True,'verification':'Exact passage checked locally. Owner must still review interpretation, historical context and modern applications.'})
 return result
