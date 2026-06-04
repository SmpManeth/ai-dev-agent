from tools.secret_mask import mask_secrets


def test_masks_bearer_token():
    text = "Authorization: Bearer abcdef1234567890"
    assert "[REDACTED]" in mask_secrets(text)


def test_masks_github_pat():
    assert "[REDACTED]" in mask_secrets("token=ghp_abcdefghijklmnopqrstuvwxyz123456")
