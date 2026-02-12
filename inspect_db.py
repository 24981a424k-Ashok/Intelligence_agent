import sys
import json
from src.database.models import SessionLocal, DailyDigest

def inspect_data():
    db = SessionLocal()
    try:
        latest = db.query(DailyDigest).filter(DailyDigest.is_published == True).order_by(DailyDigest.date.desc()).first()
        if not latest:
            print("No published digest found.")
            return

        data = latest.content_json
        
        with open("debug_output.txt", "w", encoding="utf-8") as f:
            # 1. Check Categories
            f.write("\n--- CATEGORIES ---\n")
            cats = list(data.get("categories", {}).keys())
            f.write(f"Keys: {', '.join(cats)}\n")

            # 2. Check Business Section specifically
            f.write("\n--- BUSINESS CHECK ---\n")
            biz = data.get("categories", {}).get("Business", [])
            f.write(f"Business (Title Case): {len(biz)}\n")
            biz_lower = data.get("categories", {}).get("business", [])
            f.write(f"business (Lower Case): {len(biz_lower)}\n")

            # 3. Check Image URLs
            f.write("\n--- IMAGES ---\n")
            top_stories = data.get("top_stories", [])
            img_urls = [s.get('image_url') for s in top_stories]
            unique_imgs = set(img_urls)
            f.write(f"Total Stories: {len(top_stories)}\n")
            f.write(f"Unique Images: {len(unique_imgs)}\n")
            f.write(f"First 3 Images: {img_urls[:3]}\n")

        print("Debug output written to debug_output.txt")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    inspect_data()
