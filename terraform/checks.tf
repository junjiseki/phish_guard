check "line_channel_secret_source" {
  assert {
    condition = (
      nonsensitive(var.line_channel_secret) == ""
      || var.line_channel_secret_secret_id == ""
    )
    error_message = "Set either line_channel_secret or line_channel_secret_secret_id, not both."
  }
}

check "line_channel_access_token_source" {
  assert {
    condition = (
      nonsensitive(var.line_channel_access_token) == ""
      || var.line_channel_access_token_secret_id == ""
    )
    error_message = "Set either line_channel_access_token or line_channel_access_token_secret_id, not both."
  }
}

check "gemini_api_key_source" {
  assert {
    condition = (
      nonsensitive(var.gemini_api_key) == ""
      || var.gemini_api_key_secret_id == ""
    )
    error_message = "Set either gemini_api_key or gemini_api_key_secret_id, not both."
  }
}
