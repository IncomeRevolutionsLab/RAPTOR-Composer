import os
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

# Configuration
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
DATA_DIR = "data"

def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    return gspread.authorize(credentials)

def generate_summary():
    all_files = [f for f in os.listdir(DATA_DIR) if f.startswith("comments_part_") and f.endswith(".csv")]
    
    total_comments = 0
    total_likes = 0
    unique_authors = set()
    top_commenters = pd.Series(dtype=int)
    
    print("Generating summary from collected data...")
    
    for file in all_files:
        df = pd.read_csv(os.path.join(DATA_DIR, file))
        total_comments += len(df)
        total_likes += df["like_count"].sum()
        unique_authors.update(df["author_handle"].dropna().unique())
        
        # Count top commenters
        counts = df["author_handle"].value_counts()
        top_commenters = top_commenters.add(counts, fill_value=0)

    summary = {
        "Metric": [
            "Total Comments (incl. Replies)",
            "Unique Commenters",
            "Total Likes Received",
            "Average Likes per Comment",
            "Last Updated"
        ],
        "Value": [
            total_comments,
            len(unique_authors),
            total_likes,
            round(total_likes / total_comments, 2) if total_comments > 0 else 0,
            pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        ]
    }
    
    top_10 = top_commenters.sort_values(ascending=False).head(10).reset_index()
    top_10.columns = ["Author", "Comment Count"]
    
    return pd.DataFrame(summary), top_10

def export_to_sheets():
    if not SHEET_ID or not SERVICE_ACCOUNT_FILE:
        print("Google Sheet ID or Service Account File not configured. Skipping export.")
        return

    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(SHEET_ID)
        
        # Get or create Summary sheet
        try:
            worksheet = sh.worksheet("Summary")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="Summary", rows="100", cols="10")

        summary_df, top_10_df = generate_summary()
        
        # Clear and update
        worksheet.clear()
        worksheet.update([summary_df.columns.values.tolist()] + summary_df.values.tolist(), "A1")
        
        worksheet.update("A8", [["Top 10 Commenters"]])
        worksheet.update([top_10_df.columns.values.tolist()] + top_10_df.values.tolist(), "A9")
        
        print(f"Successfully exported summary to Google Sheet: {sh.title}")
        
    except Exception as e:
        print(f"Failed to export to Google Sheets: {e}")

if __name__ == "__main__":
    export_to_sheets()
