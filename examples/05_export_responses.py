# examples/05_export_responses.py
"""
This example demonstrates how to export all of a user's responses
to a CSV file.
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ddd_api import DDDGermanPlatform, AuthenticationError
except ImportError:
    print("Error: ddd_api.py not found. Make sure it's in the parent directory or PYTHONPATH.")
    sys.exit(1)

# --- Configuration ---
JWT_TOKEN = "YOUR_JWT_TOKEN_HERE"  # <--- REPLACE WITH YOUR ACTUAL JWT TOKEN
YOUR_USER_ID = 00000  # <--- REPLACE WITH YOUR ACTUAL NUMERIC USER ID
OUTPUT_CSV_FILENAME = f"user_{YOUR_USER_ID}_ddd_responses.csv" # You can change this

if JWT_TOKEN == "YOUR_JWT_TOKEN_HERE" or YOUR_USER_ID == 00000:
    print("Please replace 'YOUR_JWT_TOKEN_HERE' and 'YOUR_USER_ID' with your actual credentials in the script.")
    sys.exit(1)

def main():
    """Main function to demonstrate exporting user responses."""
    print("Initializing DDDGerman API Client...")
    try:
        client = DDDGermanPlatform(jwt_token=JWT_TOKEN)
    except Exception as e:
        print(f"Error initializing client: {e}")
        return

    print(f"\n--- Exporting Responses for User ID: {YOUR_USER_ID} ---")
    try:
        # The export_user_responses method handles file creation.
        # It returns the path to the created file, or an empty string if no responses.
        exported_file_path = client.export_user_responses(
            user_id=YOUR_USER_ID,
            output_file=OUTPUT_CSV_FILENAME # Optional, a default name will be generated if None
        )

        if exported_file_path:
            print(f"\nSuccessfully exported responses to: {exported_file_path}")
            print("The CSV file includes columns like user_id, chapter_id, theme_name, slide_title, form_id, question, response_text, etc.")
        else:
            print(f"No responses found for user {YOUR_USER_ID}, or an error occurred during export.")

    except AuthenticationError as e:
        print(f"\nAuthentication Error: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred during export: {e}")

if __name__ == "__main__":
    main()
