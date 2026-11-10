from commitron.safety import find_secret_warnings


def test_detects_private_key_marker():
    assert "private key" in find_secret_warnings("-----BEGIN PRIVATE KEY-----")


def test_clean_diff_has_no_warning():
    assert find_secret_warnings("diff --git a/readme b/readme\n+hello world") == []


def test_detects_common_provider_tokens():
    sample = """\nGITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz123456\nSLACK=xoxb-123456789012-abcdefghij\nSTRIPE=sk_live_abcdefghijklmnop1234\n"""
    warnings = find_secret_warnings(sample)
    assert "GitHub token" in warnings
    assert "Slack token" in warnings
    assert "Stripe secret key" in warnings


def test_detects_password_assignment():
    assert "generic credential assignment" in find_secret_warnings("password=correct-horse-battery")
