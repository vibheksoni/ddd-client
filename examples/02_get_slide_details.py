# examples/02_get_slide_details.py
"""
This example demonstrates how to fetch a specific slide by its IDs
(chapter, theme, slide) and then analyze its content, including
extracting text and identifying forms.
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ddd_api import DDDGermanPlatform, AuthenticationError, NotFoundError
except ImportError:
    print("Error: ddd_api.py not found. Make sure it's in the parent directory or PYTHONPATH.")
    sys.exit(1)

# --- Configuration ---
JWT_TOKEN = "YOUR_JWT_TOKEN_HERE"  # <--- REPLACE WITH YOUR ACTUAL JWT TOKEN

# IDs for the specific slide you want to analyze.
# You can find these by:
# 1. Using 01_list_content.py to browse available content.
# 2. Navigating to the slide on dddgerman.org and observing the URL 
#    or network requests which often contain these IDs.
TARGET_KAPITEL_ID = 1  # <--- REPLACE with the Chapter ID
TARGET_THEMA_ID = 1    # <--- REPLACE with the Theme ID within that Chapter
TARGET_SLIDE_ID = 101  # <--- REPLACE with the Slide ID within that Theme

if JWT_TOKEN == "YOUR_JWT_TOKEN_HERE":
    print("Please replace 'YOUR_JWT_TOKEN_HERE' with your actual JWT token in the script.")
    sys.exit(1)
if TARGET_KAPITEL_ID == 1 and TARGET_THEMA_ID == 1 and TARGET_SLIDE_ID == 101:
     print("Please update TARGET_KAPITEL_ID, TARGET_THEMA_ID, and TARGET_SLIDE_ID with actual IDs you want to test.")
     # Allow to run with defaults for a quick check, but real data is better.

def main():
    """Main function to demonstrate fetching and analyzing a slide."""
    print("Initializing DDDGerman API Client...")
    try:
        client = DDDGermanPlatform(jwt_token=JWT_TOKEN)
    except Exception as e:
        print(f"Error initializing client: {e}")
        return

    print(f"\n--- Analyzing Slide (K: {TARGET_KAPITEL_ID}, T: {TARGET_THEMA_ID}, S: {TARGET_SLIDE_ID}) ---")
    try:
        # First, get the theme
        theme = client.get_theme_by_kapitel_thema(TARGET_KAPITEL_ID, TARGET_THEMA_ID)
        if not theme:
            print(f"Theme with ID {TARGET_THEMA_ID} in Chapter {TARGET_KAPITEL_ID} not found.")
            return

        # Then, get the slides for that theme
        slides = theme.get_slides()
        target_slide = None
        for slide_obj in slides:
            if slide_obj.id == TARGET_SLIDE_ID:
                target_slide = slide_obj
                break
        
        if not target_slide:
            print(f"Slide with ID {TARGET_SLIDE_ID} not found in Theme '{theme.name}'.")
            return

        print(f"Found Slide: ID={target_slide.id}, Title='{target_slide.title}'")

        # 1. Extract plain text content
        print("\n--- Extracted Text (first 500 chars) ---")
        extracted_text = target_slide.extract_text()
        print(extracted_text[:500] + ("..." if len(extracted_text) > 500 else ""))

        # 2. Get slide analysis (includes form details)
        print("\n--- Slide Analysis ---")
        analysis = target_slide.get_slide_analysis()
        if analysis:
            print(f"  Slide ID: {analysis['slide_id']}")
            print(f"  Title: {analysis['title']}")
            print(f"  HTML Length: {analysis['html_length']}")
            print(f"  Forms Count: {analysis['forms_count']}")
            if analysis['forms']:
                print("  Forms Details:")
                for i, form_info in enumerate(analysis['forms']):
                    print(f"    Form {i+1}:")
                    print(f"      ID: '{form_info['form_id']}'")
                    print(f"      Question: '{form_info['question']}'")
                    print(f"      Fields Count: {form_info['fields_count']}")
                    for j, field_info in enumerate(form_info['fields']):
                        print(f"        Field {j+1}: Name='{field_info['name']}', Type='{field_info['type']}', Label='{field_info['label']}', Required={field_info['required']}")
            
            print(f"\n  Potential Questions Found ({len(analysis['potential_questions'])}):")
            for pq_idx, pq_text in enumerate(analysis['potential_questions'][:5]): # Print first 5
                print(f"    {pq_idx+1}. {pq_text}")
            if len(analysis['potential_questions']) > 5:
                print("    ...")
        else:
            print("Could not get analysis for the slide.")
            
        # 3. Save HTML to file (optional)
        # html_file = target_slide.save_html_to_file()
        # print(f"\nSlide HTML content saved to: {html_file}")

    except AuthenticationError as e:
        print(f"\nAuthentication Error: {e}")
    except NotFoundError as e:
        print(f"\nNot Found Error: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
