import sys
import argparse
from collector import collect_comments
from exporter import export_to_sheets

def main():
    parser = argparse.ArgumentParser(description="YouTube Comment Analyzer")
    parser.add_argument("video_id", help="The ID of the YouTube video to analyze")
    parser.add_argument("--resume", action="store_true", help="Resume from the last checkpoint")
    parser.add_argument("--skip-export", action="store_true", help="Skip exporting to Google Sheets")
    
    args = parser.parse_args()

    print("=== YouTube Comment Analyzer ===")
    try:
        collect_comments(args.video_id, resume=args.resume)
        
        if not args.skip_export:
            print("\n=== Exporting to Google Sheets ===")
            export_to_sheets()
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Progress saved in checkpoint.json.")
    except Exception as e:
        print(f"\nAn error occurred during execution: {e}")

if __name__ == "__main__":
    main()
