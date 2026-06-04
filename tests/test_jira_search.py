"""Tests for Jira JQL search API."""

from __future__ import annotations

from unittest.mock import patch

from config import Settings
from tools.jira_tool import search_jql


@patch("tools.jira_tool._request")
def test_search_jql_uses_enhanced_endpoint(mock_request):
    mock_request.return_value = {
        "issues": [
            {
                "key": "BLV-1",
                "fields": {
                    "summary": "Test issue",
                    "description": "Details here",
                    "labels": ["ai-fix"],
                    "status": {"name": "To Do", "statusCategory": {"key": "new"}},
                    "comment": {"comments": []},
                },
            }
        ],
        "nextPageToken": None,
    }
    settings = Settings(
        jira_base_url="https://example.atlassian.net",
        jira_email="a@b.com",
        jira_api_token="token",
    )
    issues = search_jql('project = BLV', settings, max_results=10)
    assert len(issues) == 1
    assert issues[0].key == "BLV-1"
    mock_request.assert_called_once()
    assert mock_request.call_args[0][2] == "/rest/api/3/search/jql"
