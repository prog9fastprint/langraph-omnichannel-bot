import secrets
import string

# Generate 32-character alphanumeric + punctuation
alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
secret = ''.join(secrets.choice(alphabet) for _ in range(32))
print(secret)