# examples/01_list_content.py
"""
This example demonstrates how to initialize the DDDGermanPlatform client
and list basic content like chapters, themes within a chapter, and
slides within a theme.
"""
import sys
import os

# Adjust the path to import ddd_api from the parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ddd_api import DDDGermanPlatform, AuthenticationError
except ImportError:
    print("Error: ddd_api.py not found. Make sure it's in the parent directory or PYTHONPATH.")
    sys.exit(1)

# --- Configuration ---
# Obtain your JWT token by:
# 1. Logging into dddgerman.org in your browser.
# 2. Opening browser developer tools (usually F12).
# 3. Go to the "Network" tab.
# 4. Perform an action on the site (e.g., navigate to a chapter).
# 5. Look for requests to 'api.dddgerman.org'.
# 6. In the request headers, find the 'Authorization' header. It will look like 'Bearer <YOUR_TOKEN>'.
# 7. Copy the token part (without 'Bearer ').
JWT_TOKEN = "YOUR_JWT_TOKEN_HERE"  # <--- REPLACE WITH YOUR ACTUAL JWT TOKEN

if JWT_TOKEN == "YOUR_JWT_TOKEN_HERE":
    print("Please replace 'YOUR_JWT_TOKEN_HERE' with your actual JWT token in the script.")
    sys.exit(1)

def main():
    """Main function to demonstrate listing content."""
    print("Initializing DDDGerman API Client...")
    try:
        client = DDDGermanPlatform(jwt_token=JWT_TOKEN)
    except Exception as e:
        print(f"Error initializing client: {e}")
        return

    print("\n--- Fetching All Chapters ---")
    try:
        chapters = client.get_all_chapters()
        if not chapters:
            print("No chapters found or error fetching chapters.")
            return

        print(f"Found {len(chapters)} chapters:")
        for i, chapter in enumerate(chapters):
            print(f"  {i+1}. ID: {chapter.id}, Name: \"{chapter.name}\"")

        # Let's explore the first chapter if it exists
        if chapters:
            target_chapter = chapters[0]
            print(f"\n--- Themes in Chapter '{target_chapter.name}' (ID: {target_chapter.id}) ---")
            themes = target_chapter.get_themes()
            if not themes:
                print(f"No themes found in chapter '{target_chapter.name}'.")
            else:
                print(f"Found {len(themes)} themes:")
                for j, theme in enumerate(themes):
                    print(f"  {j+1}. ID: {theme.id}, Name: \"{theme.name}\" (Kapitel: {theme.kapitel_id})")

                # Let's explore the first theme of that chapter if it exists
                if themes:
                    target_theme = themes[0]
                    print(f"\n--- Slides in Theme '{target_theme.name}' (ID: {target_theme.id}, Chapter ID: {target_theme.kapitel_id}) ---")
                    # Set include_all_institutions to True if you need slides not specific to your institution
                    slides = target_theme.get_slides(include_all_institutions=False)
                    if not slides:
                        print(f"No slides found in theme '{target_theme.name}'.")
                    else:
                        print(f"Found {len(slides)} slides:")
                        for k, slide in enumerate(slides):
                            print(f"  {k+1}. ID: {slide.id}, Title: \"{slide.title}\" (Thema: {slide.thema_id})")
                            # You can also print slide.content_html for the raw HTML, but it can be very long.
                            # print(f"    Content (first 100 chars): {slide.content_html[:100]}...")
    
    except AuthenticationError as e:
        print(f"\nAuthentication Error: {e}")
        print("Please ensure your JWT_TOKEN is correct and not expired.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
