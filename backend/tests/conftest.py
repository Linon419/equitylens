import os

TEST_ENV = {
    "SECRET_KEY_ACCESS_API": "test-secret-key-with-at-least-32-characters",
    "DATABASE_URL": "postgresql://app:app@localhost:5432/equitylens",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "equitylens",
    "DB_PASS": "app",
    "DB_USER": "app",
    "OPENAI_API_KEY": "test-openai-key",
    "OPENAI_ORGANIZATION": "test-organization",
    "FIRST_SUPERUSER": "admin@example.com",
    "FIRST_SUPERUSER_PASSWORD": "test-password",
    "GOOGLE_CLIENT_ID": "test-google-client-id",
    "FRONTEND_URL": "http://localhost:3000",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_ENDPOINT_URL": "http://localhost:9000",
    "S3_BUCKET": "filings",
    "S3_ACCESS_KEY_ID": "test-access-key",
    "S3_SECRET_ACCESS_KEY": "test-secret-key",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)
