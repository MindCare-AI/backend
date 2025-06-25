#!/bin/bash

# Script to clear GitHub Copilot cache
echo "Clearing GitHub Copilot cache..."

# Find and remove Copilot cache directories
if [ -d "$HOME/.vscode/extensions/github.copilot-*" ]; then
  echo "Cleaning VS Code Copilot extension cache..."
  find "$HOME/.vscode/extensions/github.copilot-"* -name "cache" -type d -exec rm -rf {} \; 2>/dev/null || true
  echo "VS Code Copilot cache cleared."
fi

# Clear Copilot for JetBrains IDEs if they exist
if [ -d "$HOME/.config/JetBrains" ]; then
  echo "Cleaning JetBrains Copilot plugin cache..."
  find "$HOME/.config/JetBrains" -path "*/github-copilot*/cache" -type d -exec rm -rf {} \; 2>/dev/null || true
  echo "JetBrains Copilot cache cleared."
fi

echo "GitHub Copilot cache clearing complete. Please restart your IDE."
