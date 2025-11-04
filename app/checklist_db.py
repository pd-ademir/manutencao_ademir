from sqlalchemy import create_engine
import os

base_dir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(base_dir, "..", "instance", "checklist.sqlite3")

engine_checklist = create_engine(f"sqlite:///{os.path.abspath(db_path)}", echo=False)
