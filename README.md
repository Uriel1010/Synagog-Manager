# Synagogue Purchases App

**Synagogue Purchases** is a Flask‐based web application designed to manage purchases for a synagogue. It offers features such as event management, user authentication, barcode scanning (for buyers and items), manual purchase entry, and PDF report generation with support for Hebrew text and right-to-left (RTL) alignment.

---

## Features

- **User Authentication:** Secure login/logout with role-based access (admin vs. regular user).
- **Event Management:** Create, edit, and delete events with both Gregorian and Hebrew date support.
- **Buyer and Item Management:** Register buyers and items with barcode support that auto-generates unique IDs.
- **Barcode Scanning:** Use camera-based scanning for buyers, items, and prices (with fallback to manual entry).
- **PDF Report Generation:** Generate detailed PDF reports of purchases with full RTL and Hebrew formatting.
- **Admin Dashboard:** Manage buyers, items, events, and print barcode cards.

---

## Getting Started

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- A virtual environment tool (e.g., `venv` or `virtualenv`)
- (Optional) A database (SQLite for development is supported by default)

### Installation

1. **Clone the Repository:**

   ```bash
   git clone <repository-url>
   cd synagogue-purchases-app
   ```

2. **Create and Activate a Virtual Environment:**

   On Windows:

   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

   On macOS/Linux:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

   *(Make sure your `requirements.txt` includes packages such as Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-Bcrypt, Flask-WTF, ReportLab, python-bidi, and any others you may be using.)*

4. **Configure Environment Variables:**

   Create a `.env` file in the project root (if not already present) and set your secret key and other configurations:

   ```env
   SECRET_KEY=a_very_strong_random_secret_key_generated_securely
   # DATABASE_URL=sqlite:///your_database.db   # Example for SQLite
   ```

### Running the Application

To start the development server:

```bash
python -B run.py
```

Your app should now be running (e.g., http://192.168.31.103:5000). Be sure to clear your browser cache if you’re not seeing changes.

---

## Project Structure

```plaintext
synagogue-purchases-app/
├── app/
│   ├── __init__.py          # Flask app factory and extension initialization
│   ├── models.py            # SQLAlchemy models
│   ├── forms.py             # WTForms for authentication, events, buyers, items, etc.
│   ├── routes/              # Blueprints for auth, main, admin, scanning, and reports
│   └── utils/
│       ├── pdf_utils.py     # PDF generation utility using ReportLab
│       └── ...              # Other utilities (e.g., barcode utilities)
├── requirements.txt         # All Python package dependencies
├── run.py                   # Entry point for the Flask development server
├── .env                     # Environment variable configuration
└── README.md                # This file
```

---

## Troubleshooting & Caching

### Deleting pycache Folders

Remove any `__pycache__` directories in the project to ensure no stale bytecode is loaded.

### Full Server Restart

Press `Ctrl+C` to stop the server, then restart it with `python -B run.py` to bypass cached bytecode.

### Browser Cache

Clear your browser cache or use an incognito window when testing.

---

## Contributions

Contributions are welcome! Please open issues or submit pull requests with improvements or bug fixes. Make sure to follow the project's coding style and add tests for any new features.

---

## License

This project is licensed under the MIT License – see the LICENSE file for details.