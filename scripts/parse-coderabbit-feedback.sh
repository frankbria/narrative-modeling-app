#!/bin/bash
# Parses CodeRabbit feedback into structured JSON

PR_NUMBER=$1
gh api "/repos/{owner}/{repo}/pulls/${PR_NUMBER}/comments" \
    --jq '[.[] | select(.user.login == "coderabbitai") | {
        file: .path,
        line: .line,
        feedback: .body,
        severity: (if (.body | test("critical|security|vulnerability"; "i")) then "high"
                   elif (.body | test("performance|optimization"; "i")) then "medium"
                   else "low" end)
    }]'
