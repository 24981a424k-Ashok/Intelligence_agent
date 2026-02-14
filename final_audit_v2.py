from src.database.models import SessionLocal, DailyDigest
import json

def audit_digest():
    session = SessionLocal()
    try:
        latest = session.query(DailyDigest).order_by(DailyDigest.date.desc()).first()
        if not latest:
            print("No digest found.")
            return
        
        data = latest.content_json
        breaking = data.get("breaking_news", [])
        top = data.get("top_stories", [])
        countries = data.get("countries", {})
        
        print(f"Audit Results for Digest: {latest.date}")
        print(f"--- Breaking News Count: {len(breaking)} ---")
        if breaking:
            print(f"Sample Breaking (First 5):")
            for i, b in enumerate(breaking[:5]):
                print(f"  {i+1}. {b.get('headline')} [{b.get('country')}]")
        
        print(f"--- Country Nodes Check ---")
        for c, stories in countries.items():
            print(f"  {c}: {len(stories)} stories")
            
        print(f"--- Top Stories Count: {len(top)} ---")
        
    finally:
        session.close()

if __name__ == "__main__":
    audit_digest()
