
from database import engine, Base
import models

Base.metadata.create_all(bind=engine)

print("Da tao cac bang database thanh cong!")

