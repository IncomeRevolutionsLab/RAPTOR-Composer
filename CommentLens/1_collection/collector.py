import os
import json
import pandas as pd
import sys
import shutil
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from datetime import datetime

# Global stop flag for background tasks
stop_requested = False

# Root path consistency
ROOT_DIR = r"C:\Antigravity Work\youtube-comment-analyzer"
BASE_DATA_DIR = os.path.join(ROOT_DIR, "data")

if not os.path.exists(BASE_DATA_DIR):
    os.makedirs(BASE_DATA_DIR, exist_ok=True)

load_dotenv()

def get_youtube_client(api_key=None):
    key = api_key or os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise Exception("API Key Missing")
    return build("youtube", "v3", developerKey=key)

def get_video_dir(video_id, clear=False):
    video_dir = os.path.join(BASE_DATA_DIR, video_id)
    if clear and os.path.exists(video_dir):
        shutil.rmtree(video_dir)
    os.makedirs(video_dir, exist_ok=True)
    return video_dir

def collect_comments(video_id, resume=False, api_key=None):
    global stop_requested
    stop_requested = False # Reset on start
    
    try:
        youtube = get_youtube_client(api_key)
        video_dir = get_video_dir(video_id, clear=(not resume))
        
        # Get statistics with error handling
        res = youtube.videos().list(part="statistics,snippet", id=video_id).execute()
        if not res.get("items"):
            raise Exception("Video not found")
            
        total_count = int(res["items"][0]["statistics"].get("commentCount", 0))
        video_title = res["items"][0]["snippet"]["title"]
        
        # Original target count should be preserved for the UI
        display_target = total_count if total_count > 0 else 1000 

        print(f"Collection Start: {video_title} (Expected: {total_count})")
        
        next_page_token = None
        total_collected = 0
        all_data = []
        part_index = 1

        # Load from checkpoint if resume
        checkpoint_path = os.path.join(video_dir, "checkpoint.json")
        if resume and os.path.exists(checkpoint_path):
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                ckpt = json.load(f)
                next_page_token = ckpt.get("next_page_token")
                total_collected = ckpt.get("total_collected", 0)
                # We need to find the next part index
                part_index = len([f for f in os.listdir(video_dir) if f.endswith(".csv")]) + 1

        # Save initial status
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump({"total_collected": total_collected, "total_count": display_target, "video_title": video_title, "status": "running"}, f)

        # Loop until exhausted
        while not stop_requested:
            try:
                request = youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=100,
                    pageToken=next_page_token,
                    order="time" # Changed to 'time' to ensure we get all comments sequentially
                )
                response = request.execute()
            except HttpError as e:
                if e.resp.status in [403, 429]: raise Exception("API Quota Exceeded")
                raise e

            items = response.get("items", [])
            if not items and not next_page_token:
                break

            for item in items:
                if stop_requested: break
                
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                reply_count = item["snippet"]["totalReplyCount"]
                comment_id = item["id"]

                all_data.append({
                    "author_handle": snippet.get("authorDisplayName"),
                    "content": snippet.get("textDisplay"),
                    "published_at": snippet.get("publishedAt"),
                    "like_count": snippet.get("likeCount"),
                    "reply_count": reply_count,
                    "parent_id": None,
                    "is_reply": False
                })
                total_collected += 1

                if reply_count > 0:
                    try:
                        # Direct fetch for replies with pagination support
                        r_token = None
                        while True:
                            rep_req = youtube.comments().list(part="snippet", parentId=comment_id, maxResults=100, pageToken=r_token)
                            rep_res = rep_req.execute()
                            for r_item in rep_res.get("items", []):
                                r_snip = r_item["snippet"]
                                all_data.append({
                                    "author_handle": r_snip.get("authorDisplayName"),
                                    "content": r_snip.get("textDisplay"),
                                    "published_at": r_snip.get("publishedAt"),
                                    "like_count": r_snip.get("likeCount"),
                                    "parent_id": comment_id,
                                    "is_reply": True
                                })
                                total_collected += 1
                            
                            r_token = rep_res.get("nextPageToken")
                            if not r_token or stop_requested: break
                    except: pass 

                if len(all_data) >= 5000: # Changed from 1000 to 5000
                    pd.DataFrame(all_data).to_csv(os.path.join(video_dir, f"comments_part_{part_index}.csv"), index=False, encoding="utf-8-sig")
                    all_data = []
                    part_index += 1
                    # Immediate update for UI
                    with open(checkpoint_path, "w", encoding="utf-8") as f:
                        json.dump({"total_collected": total_collected, "total_count": display_target, "video_title": video_title, "status": "running"}, f)

            next_page_token = response.get("nextPageToken")
            
            # Update checkpoint every page
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump({"total_collected": total_collected, "total_count": display_target, "video_title": video_title, "next_page_token": next_page_token, "status": "running"}, f)
            
            if not next_page_token: break

        if all_data:
            pd.DataFrame(all_data).to_csv(os.path.join(video_dir, f"comments_part_{part_index}.csv"), index=False, encoding="utf-8-sig")

        # Final Success State - Keep original display_target if we want to show 1440/3547? 
        # Actually usually users want to see it reach 100%. If it collected less, 
        # it might be due to YouTube's internal hidden comments. 
        # But let's show the actual collected vs target.
        final_status = "completed" if not stop_requested else "stopped"
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump({
                "total_collected": total_collected, 
                "total_count": display_target, 
                "video_title": video_title, 
                "status": final_status, 
                "last_updated": datetime.now().isoformat()
            }, f)

    except Exception as e:
        print(f"Error: {e}")
        try:
            with open(os.path.join(get_video_dir(video_id), "checkpoint.json"), "w", encoding="utf-8") as f:
                json.dump({"error": str(e), "status": "error", "total_collected": total_collected, "total_count": display_target}, f)
        except: pass

def load_checkpoint(video_id):
    path = os.path.join(BASE_DATA_DIR, video_id, "checkpoint.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None
