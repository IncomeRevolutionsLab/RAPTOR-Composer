@echo off
echo Adding files to git...
git add backend/connectors/naver_connector.py backend/engine/raptor_engine.py backend/main.py frontend/index.html frontend/js/app.js backend/data/keyword_pools.json

echo Committing changes...
git commit -m "[v2.45] 12-Domain Logic Separation, cache config and UX updates"

echo Pushing to remote repository...
git push

echo Deployment triggered successfully!
