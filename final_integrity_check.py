import sys
import os
from datetime import datetime

# Ensure src is in path
sys.path.append(os.getcwd())

from src.database.models import SessionLocal, DailyDigest, VerifiedNews, RawNews

def run_integrity_check():
    session = SessionLocal()
    print("--- FINAL SYSTEM INTEGRITY AUDIT ---")
    
    try:
        # 1. Latest Digest Audit
        latest_digest = session.query(DailyDigest).order_by(DailyDigest.date.desc()).first()
        if not latest_digest:
            print("ERROR: No DailyDigest found!")
        else:
            print(f"Latest Digest Date: {latest_digest.date}")
            content = latest_digest.content_json
            
            # Check for title duplicates in Top Stories
            top_stories = content.get('top_stories', [])
            top_titles = [s.get('title') for s in top_stories]
            top_dupes = [t for t in set(top_titles) if top_titles.count(t) > 1]
            if top_dupes:
                print(f"WARNING: Duplicate titles in Top Stories: {top_dupes}")
            else:
                print("SUCCESS: No duplicates in Top Stories content.")
            
            # Check Breaking News overlap with Top Stories
            breaking_news = content.get('breaking_news', [])
            breaking_titles = [b.get('headline') or b.get('title') for b in breaking_news]
            overlap = set(top_titles).intersection(set(breaking_titles))
            print(f"INFO: Overlap between Top Stories and Breaking News: {len(overlap)} items.")
            
            # Check Country Nodes for specific content
            countries = content.get('countries', {})
            print(f"Country nodes present: {list(countries.keys())}")
            for c, stories in countries.items():
                if not stories:
                    print(f"WARNING: Node {c} is empty.")
                else:
                    unique_c_titles = len(set([s.get('title') for s in stories]))
                    if unique_c_titles < len(stories):
                        print(f"WARNING: Node {c} has {len(stories) - unique_c_titles} internal duplicates.")
                    else:
                        print(f"SUCCESS: Node {c}: {len(stories)} unique stories.")
        
        # 2. Image Fallback Variety Check
        from src.delivery.web_dashboard import get_fallback_image
        test_seeds = ["Apple Launch", "NVIDIA Earnings", "India Budget", "T20 World Cup", "Global Markets", "AI Breakthrough"]
        images = [get_fallback_image(s) for s in test_seeds]
        unique_images = len(set(images))
        print(f"Fallback Variety: {unique_images} unique images for {len(test_seeds)} different titles.")
        if unique_images > 1:
            print("SUCCESS: Image fallback variety confirmed.")
        else:
            print("ERROR: Image fallback is repeating!")

        # 3. DB Cleanliness
        raw_count = session.query(RawNews).count()
        ver_count = session.query(VerifiedNews).count()
        print(f"Database Stats: {raw_count} Raw, {ver_count} Verified.")

    except Exception as e:
        print(f"ERROR: Audit Crashed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    run_integrity_check()
