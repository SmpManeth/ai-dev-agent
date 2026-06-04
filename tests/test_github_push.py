from tools.github_tool import _push_non_fast_forward, is_replaceable_agent_branch


def test_agent_branch_detected():
    assert is_replaceable_agent_branch("ai-fix/BVW-1536")
    assert not is_replaceable_agent_branch("develop")


def test_non_fast_forward_message():
    err = (
        "! ai-fix/BVW-1536 -> ai-fix/BVW-1536 (non-fast-forward)\n"
        "error: failed to push some refs"
    )
    assert _push_non_fast_forward(err)


def test_stale_info_triggers_recovery():
    assert _push_non_fast_forward("! branch (stale info)")


def test_remote_lease_ref():
    from tools.github_tool import _remote_lease_ref

    assert _remote_lease_ref("ai-fix/BVW-1536") == (
        "refs/remotes/ai-agent-push-lease/ai-fix/BVW-1536"
    )
