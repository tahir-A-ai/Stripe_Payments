import pyotp

def generate_totp_secret():
    """Generate a random TOTP secret key"""
    return pyotp.random_base32()

def verify_totp_code(secret, code):
    """Verify a TOTP code against a secret"""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)

def get_current_totp_code(secret):
    """Get current TOTP code (for testing/debugging)"""
    totp = pyotp.TOTP(secret)
    return totp.now()