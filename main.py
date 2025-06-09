import pandas as pd
import tkinter as tk
from tkinter import filedialog
import os
import sys
from ytmusicapi import YTMusic
from datetime import datetime
from tqdm import tqdm

# Enable ANSI colors in Windows
if os.name == 'nt':
    os.system('color')

# Define ANSI color codes
YELLOW = '\033[93m'
RED = '\033[91m'
GREEN = '\033[92m'
RESET = '\033[0m'

# Initialize YTMusic
try:
    ytmusic = YTMusic('headers_auth.json')
    print(f"{GREEN}YTMusic successfully initialized{RESET}")
except Exception as e:
    print(f"{RED}Error initializing YTMusic: {e}{RESET}")
    sys.exit(1)

# File selection dialog
root = tk.Tk()
root.withdraw()
print("Opening file selection dialog...")
csv_file_path = filedialog.askopenfilename(
    title="Select CSV file",
    filetypes=[("CSV files", "*.csv")]
)
root.destroy()

if not csv_file_path:
    print(f"{RED}No file selected. Program terminated.{RESET}")
    sys.exit(1)

# Extract playlist name from file
playlist_name = os.path.splitext(os.path.basename(csv_file_path))[0]
print(f"Playlist name: {playlist_name}")

# Read CSV
try:
    df = pd.read_csv(csv_file_path)
    print(f"{GREEN}CSV file read successfully, found {len(df)} tracks{RESET}")
except FileNotFoundError:
    print(f"{RED}File {csv_file_path} not found.{RESET}")
    sys.exit(1)
except Exception as e:
    print(f"{RED}Error reading CSV file: {e}{RESET}")
    sys.exit(1)

# Remove duplicates
initial_count = len(df)
df = df.drop_duplicates(subset=['Track Name', 'Artist Name(s)'])
print(f"Removed {initial_count - len(df)} duplicates, {len(df)} tracks remaining")

# Create playlist
try:
    playlist_id = ytmusic.create_playlist(
        title=playlist_name,
        description=f"Playlist created from {os.path.basename(csv_file_path)} on {datetime.now().strftime('%Y-%m-%d')}",
        privacy_status="PRIVATE"
    )
    print(f"{GREEN}Created playlist: {playlist_name} (ID: {playlist_id}){RESET}")
except Exception as e:
    print(f"{RED}Error creating playlist: {e}{RESET}")
    sys.exit(1)

# Initialize files for skipped and failed tracks
output_dir = '../logs'
os.makedirs(output_dir, exist_ok=True)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
skipped_tracks_file = os.path.join(output_dir, f'skipped_tracks_{timestamp}.txt')
failed_tracks_file = os.path.join(output_dir, f'failed_tracks_{timestamp}.txt')

# Initialize lists
failed_tracks = []
successfully_added_tracks = []
track_ids = []
track_info = {}
DURATION_TOLERANCE = 10000  # ±10 seconds in milliseconds

# Process tracks with progress bar
total_tracks = len(df)
with tqdm(total=total_tracks, desc="Processing tracks", unit="track") as pbar:
    for index, (i, row) in enumerate(df.iterrows(), 1):
        track_name = row['Track Name']
        artist_name = row['Artist Name(s)']
        album_name = row.get('Album Name', '')
        duration_ms = row.get('Duration (ms)', 0)
        query = f"{track_name} {artist_name} {album_name}".strip()
        
        print(f"\nProcessing track {index}/{total_tracks}: {track_name} by {artist_name}")

        try:
            # First search: songs only
            search_results = ytmusic.search(query, filter="songs", limit=3)
            found = False
            for result in search_results:
                if result.get('resultType') != 'song':
                    continue
                track_id = result.get('videoId')
                result_title = result.get('title', '')
                result_artist = ', '.join([artist['name'] for artist in result.get('artists', [])])
                result_album = result.get('album', {}).get('name', '') if result.get('album') else ''
                result_duration = result.get('duration_seconds', 0) * 1000

                # Check track title match
                if track_name.lower() not in result_title.lower():
                    print(f"{YELLOW}Track skipped (title mismatch): {track_name} by {artist_name} "
                          f"(Found: {result_title}){RESET}")
                    with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                        f.write(f"[{index}/{total_tracks}] {track_name} by {artist_name} (Title mismatch: {result_title})\n")
                    failed_tracks.append(f"[{index}/{total_tracks}] {track_name} by {artist_name}: Title mismatch (Found: {result_title})")
                    continue

                # Check artist match
                if artist_name.lower() not in result_artist.lower():
                    print(f"{YELLOW}Track skipped (artist mismatch): {track_name} by {artist_name} "
                          f"(Found: {result_artist}){RESET}")
                    with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                        f.write(f"[{index}/{total_tracks}] {track_name} by {artist_name} (Artist mismatch: {result_artist})\n")
                    failed_tracks.append(f"[{index}/{total_tracks}] {track_name} by {artist_name}: Artist mismatch (Found: {result_artist})")
                    continue

                # Check duration
                if duration_ms and abs(duration_ms - result_duration) > DURATION_TOLERANCE:
                    print(f"{YELLOW}Track skipped (duration mismatch): {track_name} by {artist_name} "
                          f"(CSV: {duration_ms/1000}s, Found: {result_duration/1000}s){RESET}")
                    with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                        f.write(f"[{index}/{total_tracks}] {track_name} by {artist_name} (Duration mismatch: CSV {duration_ms/1000}s, Found {result_duration/1000}s)\n")
                    failed_tracks.append(f"[{index}/{total_tracks}] {track_name} by {artist_name}: Duration mismatch (CSV: {duration_ms/1000}s, Found: {result_duration/1000}s)")
                    continue

                # Check album
                if album_name and result_album and album_name.lower() not in result_album.lower():
                    print(f"{YELLOW}Track skipped (album mismatch): {track_name} by {artist_name} "
                          f"(CSV: {album_name}, Found: {result_album}){RESET}")
                    with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                        f.write(f"[{index}/{total_tracks}] {track_name} by {artist_name} (Album mismatch: CSV {album_name}, Found {result_album})\n")
                    failed_tracks.append(f"[{index}/{total_tracks}] {track_name} by {artist_name}: Album mismatch (CSV: {album_name}, Found: {result_album})")
                    continue

                track_ids.append(track_id)
                track_info[track_id] = {'name': track_name, 'artist': artist_name}
                print(f"{GREEN}Found track: {track_name} by {artist_name} (ID: {track_id}, Album: {result_album}, "
                      f"Duration: {result_duration/1000}s){RESET}")
                found = True
                break

            # Fallback to video search
            if not found:
                print(f"{YELLOW}Track not found in songs, searching videos: {track_name} by {artist_name}{RESET}")
                search_results = ytmusic.search(query, limit=3)
                for result in search_results:
                    if result.get('resultType') != 'video':
                        continue
                    track_id = result.get('videoId')
                    result_title = result.get('title', '')
                    result_artist = ', '.join([artist['name'] for artist in result.get('artists', [])]) if result.get('artists') else ''
                    result_duration = result.get('duration_seconds', 0) * 1000

                    # Check video title match
                    if track_name.lower() not in result_title.lower():
                        print(f"{YELLOW}Video skipped (title mismatch): {track_name} by {artist_name} "
                              f"(Found: {result_title}){RESET}")
                        with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                            f.write(f"[{index}/{total_tracks}] {track_name} by {artist_name} (Video title mismatch: {result_title})\n")
                        failed_tracks.append(f"[{index}/{total_tracks}] {track_name} by {artist_name}: Video title mismatch (Found: {result_title})")
                        continue

                    # Check artist match
                    if artist_name and result_artist and artist_name.lower() not in result_artist.lower():
                        print(f"{YELLOW}Video skipped (artist mismatch): {track_name} by {artist_name} "
                              f"(Found: {result_artist}){RESET}")
                        with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                            f.write(f"[{index}/{total_tracks}] {track_name} by {artist_name} (Video artist mismatch: {result_artist})\n")
                        failed_tracks.append(f"[{index}/{total_tracks}] {track_name} by {artist_name}: Video artist mismatch (Found: {result_artist})")
                        continue

                    # Check duration
                    if duration_ms and abs(duration_ms - result_duration) > DURATION_TOLERANCE:
                        print(f"{YELLOW}Video skipped (duration mismatch): {track_name} by {artist_name} "
                              f"(CSV: {duration_ms/1000}s, Found: {result_duration/1000}s){RESET}")
                        with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                            f.write(f"[{index}/{total_tracks}] {track_name} by {artist_name} (Video duration mismatch: CSV {duration_ms/1000}s, Found {result_duration/1000}s)\n")
                        failed_tracks.append(f"[{index}/{total_tracks}] {track_name} by {artist_name}: Video duration mismatch (CSV: {duration_ms/1000}s, Found: {result_duration/1000}s)")
                        continue

                    track_ids.append(track_id)
                    track_info[track_id] = {'name': track_name, 'artist': artist_name}
                    print(f"{GREEN}Found video: {track_name} by {artist_name} (ID: {track_id}, Duration: {result_duration/1000}s){RESET}")
                    found = True
                    break

            if not found:
                print(f"{YELLOW}Track or video not found or doesn't match criteria: {track_name} by {artist_name}{RESET}")
                with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{index}/{total_tracks}] {track_name} by {artist_name} (Not found or doesn't match criteria)\n")
                failed_tracks.append(f"[{index}/{total_tracks}] {track_name} by {artist_name}: Not found or doesn't match criteria")

        except Exception as e:
            print(f"{YELLOW}Error searching track '{track_name}': {e}{RESET}")
            with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                f.write(f"[{index}/{total_tracks}] {track_name} by {artist_name} (Search error: {e})\n")
            failed_tracks.append(f"[{index}/{total_tracks}] {track_name} by {artist_name}: Search error ({e})")
        
        pbar.update(1)

# Add tracks to playlist
if track_ids:
    for track_id in track_ids:
        try:
            ytmusic.add_playlist_items(playlist_id, [track_id])
            track_name = track_info[track_id]['name']
            artist_name = track_info[track_id]['artist']
            print(f"{GREEN}Added track: {track_name} by {artist_name}{RESET}")
            successfully_added_tracks.append(f"{track_name} by {artist_name}")
        except Exception as e:
            track_name = track_info.get(track_id, {'name': 'Unknown'})['name']
            artist_name = track_info.get(track_id, {'artist': 'Unknown'})['artist']
            if "HTTP 409" in str(e):
                print(f"{RED}Failed to add track: {track_name} by {artist_name}. "
                      f"Possibly already in playlist or unavailable.{RESET}")
                failed_tracks.append(f"{track_name} by {artist_name}: Failed to add (HTTP 409, possibly already in playlist or unavailable)")
            else:
                print(f"{RED}Error adding track {track_name} by {artist_name}: {e}{RESET}")
                failed_tracks.append(f"{track_name} by {artist_name}: Add error ({e})")
else:
    print(f"{YELLOW}No tracks added as none were found.{RESET}")

# Write failed tracks to file
with open(failed_tracks_file, 'w', encoding='utf-8') as f:
    filtered_failed_tracks = [track for track in failed_tracks if not any(success in track for success in successfully_added_tracks)]
    if filtered_failed_tracks:
        f.write("Failed tracks:\n")
        for track in filtered_failed_tracks:
            f.write(f"{track}\n")
    else:
        f.write("All tracks processed successfully.\n")

# Print summary
print(f"\n{GREEN}=== Process Summary ==={RESET}")
print(f"Total tracks processed: {total_tracks}")
print(f"Tracks successfully added: {len(successfully_added_tracks)}")
print(f"Tracks failed: {len(filtered_failed_tracks)}")
if filtered_failed_tracks:
    print(f"\n{RED}Tracks not found or failed:{RESET}")
    for track in filtered_failed_tracks:
        print(f"- {track}")
print(f"\nSkipped tracks log saved to: {skipped_tracks_file}")
print(f"Failed tracks log saved to: {failed_tracks_file}")
print(f"{GREEN}Process completed.{RESET}")