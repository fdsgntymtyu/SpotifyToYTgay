
from ytmusicapi import YTMusic
import pandas as pd
import sys
import tkinter as tk
from tkinter import filedialog
import os

try:
    ytmusic = YTMusic('headers_auth.json')
    print("YTMusic успешно инициализирован")
except Exception as e:
    print(f"Ошибка при инициализации YTMusic: {e}")
    sys.exit(1)


root = tk.Tk()
root.withdraw()
print("Открывается диалоговое окно для выбора CSV-файла...")
csv_file_path = filedialog.askopenfilename(
    title="Выберите CSV-файл",
    filetypes=[("CSV files", "*.csv")]
)
root.destroy()

if not csv_file_path:
    print("Файл не выбран. Программа завершена.")
    sys.exit(1)

playlist_name = os.path.splitext(os.path.basename(csv_file_path))[0]
print(f"Название плейлиста будет: {playlist_name}")


try:
    df = pd.read_csv(csv_file_path)
    print(f"CSV-файл успешно прочитан, найдено {len(df)} треков")
except FileNotFoundError:
    print(f"Файл {csv_file_path} не найден.")
    sys.exit(1)
except Exception as e:
    print(f"Ошибка при чтении CSV-файла: {e}")
    sys.exit(1)


df = df.drop_duplicates(subset=['Track Name', 'Artist Name(s)'])

try:
    playlist_id = ytmusic.create_playlist(
        title=playlist_name,
        description="Playlist created from liked_songs.csv",
        privacy_status="PRIVATE"
    )
    print(f"Создан плейлист: {playlist_name} (ID: {playlist_id})")
except Exception as e:
    print(f"Ошибка при создании плейлиста: {e}")
    sys.exit(1)

YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

track_ids = []
track_info = {}
for index, row in df.iterrows():
    track_name = row['Track Name']
    artist_name = row['Artist Name(s)']
    query = f"{track_name} {artist_name}"

    try:
        search_results = ytmusic.search(query, filter="songs", limit=1)
        if search_results and len(search_results) > 0:
            #print(f"Результат поиска для '{query}': {search_results[0]}")
            track_id = search_results[0]['videoId']
            track_ids.append(track_id)
            track_info[track_id] = {'name': track_name, 'artist': artist_name}
            print(f"Найден трек: {track_name} by {artist_name} (ID: {track_id})")
        else:
            print(YELLOW + f"Трек не найден: {track_name} by {artist_name}" + RESET)
    except Exception as e:
        print(f"Ошибка при поиске трека '{track_name}': {e}")


print(f"Собранные track_ids: {track_ids}")


if track_ids:
    for track_id in track_ids:
        try:
            ytmusic.add_playlist_items(playlist_id, [track_id])
            track_name = track_info[track_id]['name']
            artist_name = track_info[track_id]['artist']
            print(f"Добавлен трек: {track_name} by {artist_name}")
        except Exception as e:
            track_name = track_info.get(track_id, {'name': 'Неизвестно'})['name']
            artist_name = track_info.get(track_id, {'artist': 'Неизвестно'})['artist']
            if "HTTP 409" in str(e):
                print(RED + f"Не удалось добавить трек: {track_name} by {artist_name}. Возможно, трек уже в плейлисте или недоступен." + RESET)
            else:
                print(RED + f"Ошибка при добавлении трека {track_name} by {artist_name}: {e}" + RESET)
                print(f"Детали ошибки: {str(e.__dict__)}")
else:
    print("Ни один трек не был добавлен, так как ничего не найдено.")

print("Процесс завершен.")