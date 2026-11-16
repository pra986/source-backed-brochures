# GitHub repository

Destination: https://github.com/pra986/source-backed-brochures

This repository contains the AI-assisted, course-inspired brochure implementation prepared in this collaboration. It is separate from the n8m workflow repository.

Clone the repository, enter its root and follow README.md. The default branch is finance, matching the empty repository created by the owner.

## Local changes

```sh
git clone https://github.com/pra986/source-backed-brochures.git
cd source-backed-brochures
git switch -c feature/your-change
# Implement and verify the change.
python -m unittest discover -s tests -v
git add YOUR_CHANGED_FILES
git diff --cached
git commit -m "Describe the actual completed change"
git push -u origin feature/your-change
```

Open a pull request against this repository's default branch. Preserve the attribution and AI-assistance notes. Never commit .env or real API keys.
