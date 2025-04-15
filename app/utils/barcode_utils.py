# file: app/utils/barcode_utils.py
import barcode
from barcode.writer import ImageWriter, SVGWriter
import io
import base64
import logging

from app import db
from app.models import Buyer, Item
# Corrected import for SQL functions: Use func object primarily
from sqlalchemy import func, cast, Integer, String
# Removed substring, text from here (text is still valid if needed, but not used now)
# from sqlalchemy.sql.expression import text

# Configure logger for this module
logger = logging.getLogger(__name__)

# Choose the barcode type (Code 128 is good for alphanumeric)
BARCODE_TYPE = barcode.get_barcode_class('code128')

def generate_barcode_bytes(data: str, writer_format='PNG'):
    """Generates barcode image bytes."""
    if not data:
        return None
    try:
        # Writer options can control module width, text visibility etc.
        options = {'module_height': 8.0, 'font_size': 8, 'text_distance': 3.0, 'quiet_zone': 2.0}
        if writer_format.upper() == 'SVG':
            writer = SVGWriter()
        else: # Default to PNG
             # Ensure Pillow is installed for ImageWriter
             try:
                 writer = ImageWriter(format='PNG')
             except ImportError:
                  logger.error("Pillow library not found. PNG barcode generation requires Pillow. Please install it: pip install Pillow")
                  return None


        # Create an in-memory buffer
        buffer = io.BytesIO()
        # Instantiate the barcode object and write to buffer
        bc = BARCODE_TYPE(data, writer=writer)
        bc.write(buffer, options=options)
        buffer.seek(0)
        return buffer.read()
    except Exception as e:
        logger.error(f"Error generating barcode bytes for '{data}': {e}", exc_info=True)
        return None

def generate_barcode_uri(data: str, format='png'):
    """Generates a Base64 Data URI for embedding in HTML."""
    img_bytes = generate_barcode_bytes(data, writer_format=format)
    if img_bytes:
        encoded = base64.b64encode(img_bytes).decode('utf-8')
        mime_type = 'image/svg+xml' if format.lower() == 'svg' else 'image/png'
        return f"data:{mime_type};base64,{encoded}"
    return None

def generate_next_barcode_id(prefix: str, starting_num: int = 1000) -> str | None:
    """
    Generates the next available barcode ID with a given prefix.
    Example: If highest existing is B1005, returns B1006.
    Args:
        prefix (str): The prefix for the barcode (e.g., 'B' for Buyer, 'I' for Item).
        starting_num (int): The number to start with if no previous IDs exist.
    Returns:
        str | None: The next barcode ID string or None if an error occurs.
    """
    if not prefix:
        logger.error("Prefix cannot be empty for barcode generation.")
        return None

    model_class = None
    if prefix.upper() == 'B':
        model_class = Buyer
    elif prefix.upper() == 'I':
        model_class = Item
    else:
        logger.error(f"Unknown prefix '{prefix}' for barcode generation.")
        return None

    try:
        prefix_len = len(prefix)
        # *** Use func.substr for SQLite/PostgreSQL ***
        # Use func.substring for more standard SQL dialects if needed
        max_num_query = db.session.query(
            func.max(
                cast(
                    # Use the appropriate function name (substr for SQLite)
                    func.substr(model_class.barcode_id, prefix_len + 1),
                    Integer
                )
            )
        ).filter(model_class.barcode_id.like(f"{prefix}%"))

        # Debug: Print the generated SQL (optional)
        # from sqlalchemy.dialects import sqlite
        # print(max_num_query.statement.compile(dialect=sqlite.dialect()))

        max_num = max_num_query.scalar() # scalar() gets the first column of the first row, or None

        next_num = (max_num + 1) if max_num is not None else starting_num
        next_id = f"{prefix.upper()}{next_num}"

        logger.info(f"Generated next barcode ID for prefix '{prefix}': {next_id}")
        return next_id

    except Exception as e:
        logger.error(f"Database error generating next barcode ID for prefix '{prefix}': {e}", exc_info=True)
        return None