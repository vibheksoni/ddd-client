# examples/04_get_user_progress.py
"""
This example demonstrates how to fetch and display a summary of a user's
progress across chapters and themes.
"""
import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ddd_api import DDDGermanPlatform, AuthenticationError
except ImportError:
    print("Error: ddd_api.py not found. Make sure it's in the parent directory or PYTHONPATH.")
    sys.exit(1)

# --- Configuration ---
JWT_TOKEN = "YOUR_JWT_TOKEN_HERE"  # <--- REPLACE WITH YOUR ACTUAL JWT TOKEN
YOUR_USER_ID = 00000  # <--- REPLACE WITH YOUR ACTUAL NUMERIC USER ID

if JWT_TOKEN == "YOUR_JWT_TOKEN_HERE" or YOUR_USER_ID == 00000:
    print("Please replace 'YOUR_JWT_TOKEN_HERE' and 'YOUR_USER_ID' with your actual credentials in the script.")
    sys.exit(1)

def main():
    """Main function to demonstrate fetching user progress."""
    print("Initializing DDDGerman API Client...")
    try:
        client = DDDGermanPlatform(jwt_token=JWT_TOKEN)
    except Exception as e:
        print(f"Error initializing client: {e}")
        return

    print(f"\n--- Fetching Progress for User ID: {YOUR_USER_ID} ---")
    try:
        progress_data = client.get_user_progress(user_id=YOUR_USER_ID)

        if not progress_data:
            print("Could not retrieve progress data.")
            return

        print("\n--- Overall Progress Summary ---")
        print(f"Total Chapters: {progress_data.get('total_chapters', 0)}")
        print(f"Total Themes: {progress_data.get('total_themes', 0)}")
        print(f"Total Slides with Forms: {progress_data.get('total_slides', 0)}") # Note: 'total_slides' in progress refers to slides with forms
        print(f"Total Forms: {progress_data.get('total_forms', 0)}")
        print(f"Completed Forms: {progress_data.get('completed_forms', 0)}")
        print(f"Overall Completion: {progress_data.get('completion_percentage', 0.0)}%")

        print("\n--- Progress by Chapter ---")
        for chapter_prog in progress_data.get('chapters', []):
            print(f"\nChapter: {chapter_prog.get('name', 'N/A')} (ID: {chapter_prog.get('id', 'N/A')})")
            print(f"  Total Forms in Chapter: {chapter_prog.get('total_forms', 0)}")
            print(f"  Completed Forms in Chapter: {chapter_prog.get('completed_forms', 0)}")
            print(f"  Chapter Completion: {chapter_prog.get('completion_percentage', 0.0)}%")
            
            # To print theme details, uncomment below (can be verbose)
            # for theme_prog in chapter_prog.get('themes', []):
            #     print(f"    Theme: {theme_prog.get('name', 'N/A')} (ID: {theme_prog.get('id', 'N/A')})")
            #     print(f"      Completed Forms: {theme_prog.get('completed_forms',0)}/{theme_prog.get('total_forms',0)} ({theme_prog.get('completion_percentage',0.0)}%)")

        # For more detailed output, you can dump the whole structure:
        # print("\n--- Full Progress Data (JSON) ---")
        # print(json.dumps(progress_data, indent=2, ensure_ascii=False))

    except AuthenticationError as e:
        print(f"\nAuthentication Error: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
