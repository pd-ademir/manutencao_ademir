import os
from app import create_app

os.environ['AMBIENTE'] = 'local'
os.environ['FLASK_ENV'] = 'development'

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
