"""
APEC Schedule - Server Manager
GUI для управления Flask сервером
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import time
import os
import sys
import socket
import signal
import psutil

class ServerManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("APEC Schedule - Server Manager")
        self.root.geometry("400x300")
        self.root.resizable(False, False)

        # Set icon if exists
        try:
            self.root.iconbitmap("app/static/favicon.ico")
        except:
            pass

        self.process = None
        self.is_running = False
        self.output_text = None

        self.setup_ui()
        self.check_status_loop()

    def setup_ui(self):
        # Title
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        title_label = tk.Label(
            title_frame,
            text="APEC Petrotechnic",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="#2c3e50"
        )
        title_label.pack(pady=5)

        subtitle_label = tk.Label(
            title_frame,
            text="Система расписания - Управление сервером",
            font=("Arial", 10),
            fg="#bdc3c7",
            bg="#2c3e50"
        )
        subtitle_label.pack()

        # Status Frame
        status_frame = tk.LabelFrame(self.root, text="Статус сервера", padx=20, pady=10)
        status_frame.pack(fill=tk.X, padx=20, pady=10)

        self.status_indicator = tk.Canvas(status_frame, width=20, height=20, highlightthickness=0)
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 10))
        self.status_circle = self.status_indicator.create_oval(2, 2, 18, 18, fill="gray")

        self.status_label = tk.Label(
            status_frame,
            text="Проверка...",
            font=("Arial", 12)
        )
        self.status_label.pack(side=tk.LEFT)

        # URL Frame
        url_frame = tk.Frame(self.root)
        url_frame.pack(fill=tk.X, padx=20)

        self.url_label = tk.Label(
            url_frame,
            text="http://127.0.0.1:5000",
            font=("Arial", 10),
            fg="#3498db",
            cursor="hand2"
        )
        self.url_label.pack()
        self.url_label.bind("<Button-1>", self.open_browser)

        # Buttons Frame
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=20, pady=20)

        self.start_btn = tk.Button(
            btn_frame,
            text="▶ Запустить",
            font=("Arial", 11),
            bg="#27ae60",
            fg="white",
            width=15,
            height=2,
            command=self.start_server
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(
            btn_frame,
            text="■ Остановить",
            font=("Arial", 11),
            bg="#e74c3c",
            fg="white",
            width=15,
            height=2,
            command=self.stop_server,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Open Browser Button
        self.browser_btn = tk.Button(
            self.root,
            text="🌐 Открыть в браузере",
            font=("Arial", 10),
            command=self.open_browser,
            state=tk.DISABLED
        )
        self.browser_btn.pack(pady=5)

        # Log Frame
        log_frame = tk.LabelFrame(self.root, text="Последнее действие", padx=10, pady=5)
        log_frame.pack(fill=tk.BOTH, padx=20, pady=10, expand=True)

        self.log_label = tk.Label(
            log_frame,
            text="Готов к работе",
            font=("Arial", 9),
            fg="#7f8c8d",
            wraplength=350
        )
        self.log_label.pack()

    def check_port(self, port=5000):
        """Check if port is in use"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0

    def update_status(self, running):
        """Update UI based on server status"""
        self.is_running = running

        if running:
            self.status_indicator.itemconfig(self.status_circle, fill="#27ae60")
            self.status_label.config(text="Сервер работает", fg="#27ae60")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.browser_btn.config(state=tk.NORMAL)
        else:
            self.status_indicator.itemconfig(self.status_circle, fill="#e74c3c")
            self.status_label.config(text="Сервер остановлен", fg="#e74c3c")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.browser_btn.config(state=tk.DISABLED)

    def check_status_loop(self):
        """Periodically check server status"""
        running = self.check_port(5000)
        self.update_status(running)
        self.root.after(2000, self.check_status_loop)  # Check every 2 seconds

    def start_server(self):
        """Start the Flask server"""
        if self.is_running:
            messagebox.showinfo("Информация", "Сервер уже запущен!")
            return

        self.log_label.config(text="Запуск сервера...")

        def run_server():
            try:
                # Get the directory of this script
                script_dir = os.path.dirname(os.path.abspath(__file__))

                # Start the server
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

                self.process = subprocess.Popen(
                    [sys.executable, "run.py"],
                    cwd=script_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )

                # Wait a bit and check if started
                time.sleep(2)

                if self.check_port(5000):
                    self.root.after(0, lambda: self.log_label.config(
                        text=f"Сервер запущен (PID: {self.process.pid})",
                        fg="#27ae60"
                    ))
                else:
                    self.root.after(0, lambda: self.log_label.config(
                        text="Ошибка запуска сервера",
                        fg="#e74c3c"
                    ))

            except Exception as e:
                self.root.after(0, lambda: self.log_label.config(
                    text=f"Ошибка: {str(e)[:50]}",
                    fg="#e74c3c"
                ))

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

    def find_processes_on_port(self, port):
        """Find all processes listening on port using psutil"""
        pids = []
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr.port == port and conn.status == 'LISTEN':
                    if conn.pid:
                        pids.append(conn.pid)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
        return list(set(pids))

    def find_run_py_processes(self):
        """Find all python processes running run.py"""
        pids = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline']
                        if cmdline and any('run.py' in arg for arg in cmdline):
                            pids.append(proc.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except:
            pass
        return pids

    def stop_server(self):
        """Stop the Flask server"""
        self.log_label.config(text="Остановка сервера...")
        self.stop_btn.config(state=tk.DISABLED)

        def kill_server():
            killed_count = 0
            try:
                # Method 1: Kill our stored process and its children
                if self.process and self.process.poll() is None:
                    try:
                        parent = psutil.Process(self.process.pid)
                        children = parent.children(recursive=True)
                        for child in children:
                            try:
                                child.kill()
                                killed_count += 1
                            except:
                                pass
                        parent.kill()
                        killed_count += 1
                        self.process = None
                    except:
                        pass

                # Method 2: Find and kill by port using psutil
                port_pids = self.find_processes_on_port(5000)
                for pid in port_pids:
                    try:
                        proc = psutil.Process(pid)
                        children = proc.children(recursive=True)
                        for child in children:
                            try:
                                child.kill()
                                killed_count += 1
                            except:
                                pass
                        proc.kill()
                        killed_count += 1
                    except:
                        pass

                # Method 3: Find run.py processes
                run_py_pids = self.find_run_py_processes()
                for pid in run_py_pids:
                    try:
                        proc = psutil.Process(pid)
                        proc.kill()
                        killed_count += 1
                    except:
                        pass

                time.sleep(1.5)

                if not self.check_port(5000):
                    self.root.after(0, lambda: self.log_label.config(
                        text=f"Сервер остановлен (процессов: {killed_count})",
                        fg="#27ae60"
                    ))
                else:
                    self.root.after(0, lambda: self.log_label.config(
                        text="Не удалось остановить. Попробуйте вручную.",
                        fg="#e74c3c"
                    ))

            except Exception as e:
                self.root.after(0, lambda: self.log_label.config(
                    text=f"Ошибка: {str(e)[:50]}",
                    fg="#e74c3c"
                ))

        thread = threading.Thread(target=kill_server, daemon=True)
        thread.start()

    def open_browser(self, event=None):
        """Open the application in browser"""
        if self.is_running:
            import webbrowser
            webbrowser.open("http://127.0.0.1:5000")

    def on_closing(self):
        """Handle window close"""
        if self.is_running and self.process:
            if messagebox.askyesno("Выход", "Сервер запущен. Остановить его перед выходом?"):
                self.stop_server()
                time.sleep(2)
        self.root.destroy()

    def run(self):
        """Run the application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


if __name__ == "__main__":
    app = ServerManager()
    app.run()
