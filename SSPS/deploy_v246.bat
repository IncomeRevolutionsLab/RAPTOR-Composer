@echo off
echo Adding files to git...
git add frontend/index.html frontend/js/app.js

echo Committing changes...
git commit -m "[v2.46] Bugfix: Extend fetch timeout to 60s for Render cold start and bust cache"

echo Pushing to remote repository...
git push

echo Deployment triggered successfully!
