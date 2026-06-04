from tools.test_tool import validation_used_weak_checks


def test_weak_checks_detected():
    assert validation_used_weak_checks(
        "Validation passed: patch only changes non-PHP files"
    )


def test_npm_pass_not_weak():
    assert not validation_used_weak_checks("npm run test\nexit code: 0")
