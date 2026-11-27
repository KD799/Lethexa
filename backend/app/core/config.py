import os
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)

if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError("A secure JWT_SECRET of at least 32 characters is required")

if JWT_ALGORITHM != "HS256":
    raise RuntimeError("Unsupported JWT algorithm")