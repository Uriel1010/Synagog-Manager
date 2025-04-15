# file: run.py
from app import create_app, db
# Import models needed for shell context if desired
from app.models import User, Event, Buyer, Item, Purchase

app = create_app()

# Optional: Add context for 'flask shell'
@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Event': Event, 'Buyer': Buyer, 'Item': Item, 'Purchase': Purchase}

if __name__ == '__main__':
    # Use app.run() only for development.
    # For production, use a WSGI server like Gunicorn:
    # gunicorn -w 4 'run:app'
    app.config['DEBUG'] = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.run(debug=True, host='192.168.31.103') # Turn debug=False for production