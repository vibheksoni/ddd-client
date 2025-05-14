<div align="center">
  <img src="https://placehold.co/150x150/0D6EFD/white?text=DDD&font=roboto" alt="DDDGerman API Client Logo" width="150" />
  <h1>DDDGerman API Client</h1>
  <p>
    <b>An advanced, unofficial Python client for the DDDGerman learning platform API.</b><br>
    Effortlessly automate, analyze, and interact with your German language exercises.
  </p>
  <p>
    <a href="https://github.com/vibheksoni/ddd-client/stargazers"><img src="https://img.shields.io/github/stars/vibheksoni/ddd-client?style=social" alt="GitHub Stars"/></a>
    <img src="https://img.shields.io/pypi/pyversions/requests?label=python&logo=python&logoColor=white&color=0D6EFD" alt="Python Version"/>
    <a href="https://github.com/vibheksoni/ddd-client/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"/></a>
    <img src="https://img.shields.io/badge/status-beta-orange" alt="Status: Beta"/>
  </p>
</div>

---

## 🚀 Overview

**DDDGerman API Client** is a powerful, reverse-engineered Python library for interacting with the [DDDGerman](https://dddgerman.org) learning platform. It enables you to programmatically access, analyze, and manage your German language learning content—making automation, data extraction, and custom workflows a breeze.

Whether you're a student, educator, or developer, this tool unlocks new possibilities for engaging with your learning data.

---

## 🤔 Motivation

I originally built this project because I had to complete assignments for a German class and wanted to avoid repetitive manual work. By inspecting the frontend sources of DDDGerman, I figured out how the API works—allowing me to fetch questions, retrieve and submit answers, and automate the entire process.

To make the codebase more robust and maintainable, I used AI tools to clean up, refactor, and document the client, resulting in a much more readable and user-friendly library.

While I used this API client as the foundation for an AI-powered question solver (which I won't be publishing), I'm sharing the reversed API client itself. This way, you can easily build your own automation, analysis tools, or even your own solver if you wish. The client gives you full programmatic access to your learning data—what you do with it is up to you!

---

## 🌟 Features

- **Seamless Authentication:** Connect securely with your JWT token.
- **Comprehensive Content Access:**
  - Fetch all chapters, themes, slides, and vocabulary.
  - Drill down into specific chapters, themes, or slides by ID.
- **Powerful Data Interaction:**
  - Extract and analyze slide content, including HTML forms and questions.
  - Submit and validate answers programmatically.
  - View and export your previous responses.
- **User Progress Tracking:**
  - Get detailed progress reports by chapter, theme, or overall.
  - Export all your responses to CSV for offline review.
- **Developer-Friendly Utilities:**
  - Parse JWT tokens and HTML forms with ease.
  - Well-documented classes and methods for rapid integration.

---

## ✨ AI-Assisted Development

This project combines human ingenuity with AI-powered refinement:

- **Reverse Engineering:** Manual API discovery and protocol analysis.
- **AI Code Enhancement:** Leveraged AI for code cleanup, docstrings, type hints, and PEP 8 formatting.
- **Readable & Maintainable:** Clear structure, comprehensive documentation, and robust error handling.

---

## 📦 Installation & Setup

### 1. Prerequisites

- Python 3.7 or newer
- `ddd_api.py` (from this repo) in your project directory or Python path

### 2. Install Dependencies

Install required libraries via pip:

```bash
pip install requests beautifulsoup4
```

Or, if you prefer:

```bash
pip install -r requirements.txt
```

---

## 🚦 Quick Start

Here's how to get up and running in minutes:

```python
# Ensure ddd_api.py is in your working directory or PYTHONPATH
from ddd_api import DDDGermanPlatform, AuthenticationError, NotFoundError

# 1. Obtain your JWT token:
#    - Log in to dddgerman.org
#    - Inspect network requests for 'Authorization: Bearer <YOUR_TOKEN>'
jwt_token = "YOUR_JWT_TOKEN_HERE"  # Replace with your actual token

# 2. Find your numeric User ID (required for user-specific actions)
user_id = 12345  # Replace with your actual User ID

try:
    client = DDDGermanPlatform(jwt_token=jwt_token)
    print("\nFetching chapters...")
    chapters = client.get_all_chapters()
    if chapters:
        print(f"Found {len(chapters)} chapters.")
        first_chapter = chapters[0]
        # ...explore further as needed...
    else:
        print("No chapters found.")

except AuthenticationError as e:
    print(f"Authentication Error: {e}. Check your JWT token.")
except NotFoundError as e:
    print(f"Not Found Error: {e}. Resource missing.")
except Exception as e:
    print(f"Unexpected error: {e}")
```

---

## 📚 Examples

Explore the [`examples/`](examples/) folder for ready-to-run scripts:

| Script                      | Description                                                                 |
|-----------------------------|-----------------------------------------------------------------------------|
| `01_list_content.py`        | List chapters, themes, and slides—great for exploring content.              |
| `02_get_slide_details.py`   | Fetch and analyze a slide, extract text and form fields.                    |
| `03_submit_answer.py`       | Submit answers to forms programmatically.                                   |
| `04_get_user_progress.py`   | Display a summary of your progress, including completion stats.             |
| `05_export_responses.py`    | Export all your responses to CSV for offline review or backup.              |

**Tip:** Replace placeholder values (JWT token, User ID, etc.) with your actual data before running.

---

## 🛡️ Disclaimer

> **Unofficial Project:**  
> This client is not affiliated with or endorsed by dddgerman.org. The API may change at any time, potentially breaking compatibility. Use responsibly and at your own risk.

---

## 🤝 Contributing

Contributions are welcome! Want to add features, fix bugs, or improve docs? Here's how:

1. **Fork** [the repository](https://github.com/vibheksoni/ddd-client)
2. **Create a branch:**  
   `git checkout -b feature/YourFeature`
3. **Make your changes**
4. **Commit:**  
   `git commit -m 'Add some feature'`
5. **Push:**  
   `git push origin feature/YourFeature`
6. **Open a Pull Request**

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">
  <sub>
    Made with ❤️ by <a href="https://github.com/vibheksoni">vibheksoni</a> & contributors.
  </sub>
</div>