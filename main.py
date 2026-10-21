from tkinter import Tk, ttk, filedialog, messagebox, END
from datetime import datetime
import lz4.block
import threading
import json
import os

MOZILLA = b"mozLz40\x00"
cancel_event = threading.Event()
select_path = ""

############################################################


def decompress_jsonlz4_file(path):
    with open(path, "rb") as f:
        raw = f.read()

    if not raw.startswith(MOZILLA):
        raise ValueError("Файл не является сессией Firefox")

    return lz4.block.decompress(raw[8:])


def get_tab_url(path, progress=None):
    data = decompress_jsonlz4_file(path)
    session = json.loads(data.decode("utf-8"))

    all_tab = []
    for window in session.get("windows", []):
        for tab in window.get("tabs", []):
            all_tab.append(tab)

    total = len(all_tab)
    lines = []

    if total == 0:
        if progress:
            progress(100)
        return lines

    for index, tab in enumerate(all_tab, start=1):
        if cancel_event.is_set():
            return lines

        entries = tab.get("entries", [])
        if entries:
            last = entries[-1]
            url = last.get("url", "")
            title = last.get("title", "").strip().replace("\n", " ").replace("\r", " ")
            if url:
                lines.append(title if title else "Заголовок не найден")
                lines.append(url)

        percent = int(index / total * 100)
        if progress and (percent % 10 == 0 or index == total):
            progress(percent)

    return lines


def save_urls_to_txt(lines, save_path):
    blocks = []

    for i in range(0, len(lines) - 1, 2):
        title = lines[i]
        url = lines[i + 1]
        blocks.append(f"{title}\n{url}")
    text = "\n\n".join(blocks)

    with open(save_path, "w", encoding="utf-8") as out:
        out.write(text)


def browse_file():
    global select_path

    path = filedialog.askopenfilename(
        title="Выберите файл recovery.jsonlz4",
        filetypes=[
            ("Сессия Firefox", "*.jsonlz4"),
            ("Все файлы", "*.*"),
        ],
    )

    if not path:
        return
    select_path = path

    path_entry.delete(0, END)
    path_entry.insert(0, path)


def find_session_file():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None

    profiles_directory = os.path.join(appdata, "Mozilla", "Firefox", "Profiles")
    if not os.path.isdir(profiles_directory):
        return None

    wanted = ("recovery.jsonlz4", "sessionstore.jsonlz4")
    candidates = []

    for root, _, files in os.walk(profiles_directory):
        for name in files:
            if name in wanted:
                full_path = os.path.join(root, name)
                candidates.append(full_path)
    if not candidates:
        return None

    return sorted(candidates)[0]


def find_path_button():
    global select_path

    path = find_session_file()
    if not path:
        messagebox.showwarning(title="Внимание", message="Не удалось найти файл сессии Firefox")
        return
    select_path = path

    path_entry.delete(0, END)
    path_entry.insert(0, path)


def work(path_to_file, save_path):
    try:
        def report(percent):
            root.after(0, lambda p=percent: progressbar.configure(value=p))
        report(0)

        lines = get_tab_url(path_to_file, progress=report)
        if cancel_event.is_set():
            return

        save_urls_to_txt(lines, save_path)
        tab_count = len(lines) // 2
        root.after(0, lambda: messagebox.showinfo("Готово", f"Сохранено {tab_count} вкладок"))

    except Exception as e:
        root.after(0, lambda err=str(e): messagebox.showerror(title="Ошибка", message=err))

    finally:
        root.after(0, enable_interface)


def start():
    if not select_path:
        messagebox.showwarning(title="Внимание", message="Сначала выберите файл сессии")
        return

    template = f"firefox_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_tab.txt"
    save_path = filedialog.asksaveasfilename(
        title="Куда сохранить результат",
        defaultextension=".txt",
        filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")],
        initialfile=template
    )

    if not save_path:
        return

    cancel_event.clear()
    progressbar.configure(value=0)
    disable_interface()

    t = threading.Thread(target=work, args=(select_path, save_path), daemon=True)
    t.start()


def stop():
    cancel_event.set()
    messagebox.showinfo(title="Отмена", message="Процесс был остановлен")


############################################################


def block_input(event):
    if event.state & 0x0004 and event.keycode == 65:
        event.widget.event_generate("<<SelectAll>>")
        return "break"
    if event.state & 0x0004 and event.keycode == 67:
        event.widget.event_generate("<<Copy>>")
        return "break"
    if event.keycode in (37, 39, 36, 35):
        return None
    return "break"


def enable_interface():
    path_entry.configure(state="normal")
    browse_button.configure(state="normal")
    find_button.configure(state="normal")
    start_button.configure(state="normal")
    stop_button.configure(state="disabled")


def disable_interface():
    path_entry.configure(state="disabled")
    browse_button.configure(state="disabled")
    find_button.configure(state="disabled")
    start_button.configure(state="disabled")
    stop_button.configure(state="normal")


############################################################

root = Tk()
root.title("Firefox Tab Exporter")
root.geometry("360x180")
root.resizable(width=False, height=False)

ttk.Frame(relief="solid").place(x=5, y=5, width=350, height=85)
ttk.Label(text="Путь к файлу сессии (recovery.jsonlz4)").place(x=10, y=10)

path_entry = ttk.Entry()
path_entry.bind("<Key>", block_input)
path_entry.place(x=10, y=30, width=255)

browse_button = ttk.Button(text="Обзор", command=browse_file)
browse_button.place(x=270, y=28, width=80)

find_button = ttk.Button(text="Найти путь к файлу сессии автоматически", command=find_path_button)
find_button.place(x=10, y=60, width=340)

progressbar = ttk.Progressbar(orient="horizontal")
progressbar.place(x=10, y=115, width=340)

start_button = ttk.Button(text="Сохранить данные", command=start)
start_button.place(x=10, y=145, width=168)

stop_button = ttk.Button(text="Отмена", state="disabled", command=stop)
stop_button.place(x=182, y=145, width=168)

root.mainloop()
