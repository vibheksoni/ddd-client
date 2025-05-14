# examples/03_submit_answer.py
"""
This example demonstrates how to submit an answer to a specific form on a slide.
It requires you to know the Chapter ID, Theme ID, Slide ID, Form ID,
the name of the form field, and your numeric User ID.
"""
import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ddd_api import DDDGermanPlatform, AuthenticationError, NotFoundError, FormSubmissionError
except ImportError:
    print("Error: ddd_api.py not found. Make sure it's in the parent directory or PYTHONPATH.")
    sys.exit(1)

# --- Configuration ---
JWT_TOKEN = "YOUR_JWT_TOKEN_HERE"  # <--- REPLACE WITH YOUR ACTUAL JWT TOKEN

# Your numeric User ID from the DDDGerman platform.
# This is essential for submitting answers under your account.
# You might find this in your profile URL or by inspecting API calls your browser makes.
YOUR_USER_ID = 00000  # <--- REPLACE WITH YOUR ACTUAL NUMERIC USER ID 

# IDs for the specific form you want to submit an answer to.
# Use 01_list_content.py and 02_get_slide_details.py to find these.
TARGET_KAPITEL_ID = 1  # <--- REPLACE
TARGET_THEMA_ID = 1    # <--- REPLACE
TARGET_SLIDE_ID = 101  # <--- REPLACE
TARGET_FORM_ID = "form_exercise_123" # <--- REPLACE (e.g., "form-1", "dddgerman-exercise-xyz")
                                     # This is the 'form_id' from slide analysis or FormParser

# The data to submit. This must be a dictionary where keys are the 'name' attributes
# of the form fields (<input name="fieldName">) and values are the answers.
# For simple text inputs, it might be like: {"answer_field_name": "My submitted text"}
# For multiple choice, it might be: {"multiple_choice_name": "value_of_selected_option"}
# Inspect the form HTML or use 02_get_slide_details.py to find field names.
FORM_DATA_TO_SUBMIT = {
    "antwortInput": "This is my answer submitted via the API." 
    # <--- REPLACE "antwortInput" with the actual field name from the form
    # <--- REPLACE the value with your desired answer.
}

if JWT_TOKEN == "YOUR_JWT_TOKEN_HERE" or YOUR_USER_ID == 00000:
    print("Please replace 'YOUR_JWT_TOKEN_HERE' and 'YOUR_USER_ID' with your actual credentials in the script.")
    sys.exit(1)
if TARGET_KAPITEL_ID == 1 and TARGET_FORM_ID == "form_exercise_123":
    print("Please update TARGET_KAPITEL_ID, TARGET_THEMA_ID, TARGET_SLIDE_ID, TARGET_FORM_ID, and FORM_DATA_TO_SUBMIT with actual details.")
    # Allow to run, but it will likely fail without correct IDs.

def main():
    """Main function to demonstrate submitting an answer."""
    print("Initializing DDDGerman API Client...")
    try:
        client = DDDGermanPlatform(jwt_token=JWT_TOKEN)
    except Exception as e:
        print(f"Error initializing client: {e}")
        return

    print(f"\n--- Attempting to Submit Answer ---")
    print(f"User ID: {YOUR_USER_ID}")
    print(f"Target: K={TARGET_KAPITEL_ID}, T={TARGET_THEMA_ID}, S={TARGET_SLIDE_ID}, Form='{TARGET_FORM_ID}'")
    print(f"Data to submit: {json.dumps(FORM_DATA_TO_SUBMIT)}")

    try:
        # 1. Get the theme
        theme = client.get_theme_by_kapitel_thema(TARGET_KAPITEL_ID, TARGET_THEMA_ID)
        if not theme:
            print(f"Theme with ID {TARGET_THEMA_ID} in Chapter {TARGET_KAPITEL_ID} not found.")
            return

        # 2. Create a Form handler using the theme
        #    Note: The Form class itself doesn't fetch the slide, it's a handler.
        #    The submit_form_data method will make the API call.
        form_handler = theme.create_form(
            user_id=YOUR_USER_ID,
            form_id=TARGET_FORM_ID,
            slide_id=TARGET_SLIDE_ID
            # kapitel_id and thema_id are already part of the theme object
        )
        
        # Optional: You can retrieve and print the form structure before submitting
        # form_structure = form_handler.get_form_data()
        # if form_structure:
        #     print(f"\nForm Structure for '{TARGET_FORM_ID}':")
        #     print(f"  Question: {form_structure.question_text}")
        #     for field in form_structure.fields:
        #         print(f"  Field: Name='{field.name}', Type='{field.field_type.name}', Label='{field.label}'")
        # else:
        #     print(f"Could not retrieve structure for form '{TARGET_FORM_ID}'. Submission might fail if IDs are incorrect.")

        # 3. Submit the form data
        print("\nSubmitting form data...")
        submitted_response = form_handler.submit_form_data(FORM_DATA_TO_SUBMIT)
        
        print("\n--- Submission Successful ---")
        print(f"Response ID: {submitted_response.id}")
        print(f"Submitted Form ID: {submitted_response.form_id}")
        print(f"Submitted Slide ID: {submitted_response.slide_id}")
        print(f"Response Text (if applicable): {submitted_response.response_text}")
        print(f"Raw Form Data Submitted: {submitted_response.form_data_raw}")
        print(f"Created At: {submitted_response.created_at}")
        print(f"Updated At: {submitted_response.updated_at}")

    except AuthenticationError as e:
        print(f"\nAuthentication Error: {e}")
    except NotFoundError as e:
        print(f"\nNot Found Error: {e}. Check if Chapter/Theme/Slide IDs are correct.")
    except FormSubmissionError as e:
        print(f"\nForm Submission Error: {e}")
        print("This could be due to incorrect form field names, invalid data, or server-side validation.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
