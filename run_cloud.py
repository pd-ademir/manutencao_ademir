import os
from app import create_app

os.environ['AMBIENTE'] = 'cloud'
os.environ['FLASK_ENV'] = 'production'

app = create_app()

if __name__ == "__main__":
    app.run(debug=False)
