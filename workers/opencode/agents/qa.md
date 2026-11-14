---
description: haring qa worker — started by haring-worker, not for direct use
mode: primary
hidden: true
model: opencode-go/deepseek-v4.1-flash
permissions:
  - { action: "question", resource: "*", effect: "deny" }
  - { action: "subagent", resource: "*", effect: "deny" }
  - { action: "skill", resource: "*", effect: "deny" }
  - { action: "webfetch", resource: "*", effect: "deny" }
  - { action: "websearch", resource: "*", effect: "deny" }
  - { action: "shell", resource: "*.zsh_history*", effect: "deny" }
  - { action: "shell", resource: "*.bash_history*", effect: "deny" }
  - { action: "shell", resource: "*/.ssh*", effect: "deny" }
  - { action: "shell", resource: "*/.aws*", effect: "deny" }
  - { action: "shell", resource: "*/.config/gcloud*", effect: "deny" }
  - { action: "shell", resource: "*/.claude/*", effect: "deny" }
  - { action: "shell", resource: "*/.claude", effect: "deny" }
  - { action: "edit", resource: "*", effect: "deny" }
---
