import json
import subprocess
import re
import os
from datetime import datetime
from typing import List, Dict, Any
from openai import OpenAI

# OpenAI API 키 설정
client = OpenAI()

def get_git_commits_since_version(version: str) -> List[Dict[str, str]]:
    """Get git commit history since the specified version."""
    try:
        # Get commit messages since the specified version
        cmd = f'git log v{version}..HEAD --pretty=format:"%h|%s|%ad" --date=short'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        commits = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            commit_hash, message, date = line.split('|')
            commits.append({
                'hash': commit_hash,
                'message': message,
                'date': date
            })
        return commits
    except Exception as e:
        print(f"Error getting git commits: {e}")
        return []

def get_latest_git_tag() -> str:
    """Get the latest git tag."""
    try:
        cmd = 'git describe --tags --abbrev=0'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip().lstrip('v')
    except Exception as e:
        print(f"Error getting latest git tag: {e}")
        return ""

def organize_changes_with_gpt(commits: List[Dict[str, str]]) -> List[str]:
    """Organize commit messages into structured changes using GPT-4o-mini."""
    try:
        # Prepare commit messages for GPT
        commit_messages = "\n".join([f"- {commit['message']}" for commit in commits])
        
        # Create prompt for GPT
        prompt = f"""[Task]
            Read the **Git commit message list** below and create a concise CHANGELOG section
            for a release note.

            [How]
            1. **Group** commits that deal with the same feature, bug, or topic into a single
            bullet.
            2. Write each bullet from the **end-user’s perspective**, highlighting benefits
            and visible impact. Skip refactors, comment tweaks, or other internal chores.
            3. Start every bullet with “- ” and a **present-tense verb** (e.g., “Add”,
            “Fix”, “Improve”).
            4. (Optional) Prefix bullets with a category in square brackets —
            **[Added], [Changed], [Fixed], [Removed]** — and list categories in that
            order.
            5. Keep each bullet to one line (≈80 characters max) for quick scanning.
            6. If a commit’s purpose is unclear or has no user-facing effect, feel free to
            omit it.

            [Input]
            {commit_messages}
        
            [Output]
            Please provide a list of organized changes, one per line, starting with '- '."""
        
        # Get response from GPT-4o-mini
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a technical writer creating release notes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        # Extract and clean the changes
        changes = response.choices[0].message.content.strip().split('\n')
        changes = [change.strip('- ').strip() for change in changes if change.strip()]
        
        return changes
    except Exception as e:
        print(f"Error organizing changes with GPT: {e}")
        return [commit['message'] for commit in commits]  # Fallback to raw commit messages

def update_manifest():
    """Update the update_manifest.json file with new version information."""
    try:
        # Read current manifest
        with open('update_manifest.json', 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        current_version = manifest['latest_version']
        latest_git_tag = get_latest_git_tag()
        
        if latest_git_tag and latest_git_tag != current_version:
            # Get commits since current version
            commits = get_git_commits_since_version(current_version)
            
            if commits:
                # Organize changes using GPT
                changes = organize_changes_with_gpt(commits)
                
                # Create new version entry
                new_version = {
                    'version': latest_git_tag,
                    'release_date': datetime.now().strftime('%Y-%m-%d'),
                    'download_url': manifest['download_url'],  # You'll need to update this URL
                    'changes': changes
                }
                
                # Update manifest
                manifest['latest_version'] = latest_git_tag
                manifest['update_history'].insert(0, new_version)
                
                # Save updated manifest
                with open('update_manifest.json', 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=4, ensure_ascii=False)
                
                print(f"Updated manifest to version {latest_git_tag}")
            else:
                print("No new commits found since current version")
        else:
            print("No new version found")
            
    except Exception as e:
        print(f"Error updating manifest: {e}")

if __name__ == "__main__":
    update_manifest() 