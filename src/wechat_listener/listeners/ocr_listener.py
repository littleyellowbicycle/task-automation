"""WeChat listener using OCR screen capture."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import threading
import time
from collections import deque
from datetime import datetime
from queue import Queue, Empty
from typing import Any, Dict, List, Optional, Tuple

from ..base import BaseListener, ListenerType, Platform
from ..models import WeChatMessage, TaskMessage, MessageType, ConversationType
from ..parser import MessageParser
from ...utils import get_logger
from ...exceptions import WeChatConnectionError

logger = get_logger("wechat_listener.ocr")

PADDLEOCR_AVAILABLE = False
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PaddleOCR = None

PIL_AVAILABLE = False
try:
    from PIL import ImageGrab, Image
    PIL_AVAILABLE = True
except ImportError:
    ImageGrab = None
    Image = None

WINDOWS_API_AVAILABLE = False
try:
    import ctypes
    from ctypes import wintypes
    WINDOWS_API_AVAILABLE = True
except ImportError:
    ctypes = None

UIAUTOMATION_AVAILABLE = False
try:
    import uiautomation as auto
    UIAUTOMATION_AVAILABLE = True
except ImportError:
    auto = None


class OCRListener(BaseListener):
    """
    WeChat message listener using OCR screen capture.

    Captures screenshots of the WeChat/WeCom window at regular intervals,
    uses PaddleOCR to extract text, and detects new messages by comparing
    with previous captures.

    This approach works with self-drawn UI applications like WeCom that
    do not expose standard UIAutomation controls.
    """

    WINDOW_TITLES = {
        Platform.WEWORK: ["企业微信", "WeCom"],
        Platform.WECHAT: ["微信", "WeChat"],
    }

    def __init__(
        self,
        platform: Platform = Platform.WEWORK,
        poll_interval: float = 2.0,
        keywords: Optional[List[str]] = None,
        regex_patterns: Optional[List[str]] = None,
        ocr_model_dir: Optional[str] = None,
        crop_ratio: Tuple[float, float, float, float] = (0.22, 0.0, 1.0, 0.92),
        message_region_height: int = 200,
    ):
        super().__init__(platform=platform, keywords=keywords, regex_patterns=regex_patterns)
        self.poll_interval = poll_interval
        self.parser = MessageParser(keywords=keywords, regex_patterns=regex_patterns)
        self._message_queue: Queue = Queue()
        self._ocr: Optional[Any] = None
        self._wechat_window = None
        self._window_rect: Optional[Tuple[int, int, int, int]] = None
        self._prev_text_lines: List[str] = []
        self._prev_hash: str = ""
        self._seen_messages: deque = deque(maxlen=500)
        self._seen_set: set = set()
        self._listener_thread: Optional[threading.Thread] = None
        self._ocr_model_dir = ocr_model_dir
        self._crop_ratio = crop_ratio
        self._message_region_height = message_region_height
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def listener_type(self) -> ListenerType:
        return ListenerType("ocr")

    async def connect(self) -> bool:
        if not PADDLEOCR_AVAILABLE:
            raise WeChatConnectionError(
                "paddleocr is not installed. Install with: pip install paddleocr paddlepaddle"
            )
        if not PIL_AVAILABLE:
            raise WeChatConnectionError(
                "Pillow is not installed. Install with: pip install Pillow"
            )

        logger.info(f"Initializing OCR listener for {self.platform.value}...")

        self._init_ocr()

        self._wechat_window = self._find_wechat_window()
        if not self._wechat_window:
            raise WeChatConnectionError(
                f"Could not find {self.platform.value} window. "
                f"Please ensure it is running and visible."
            )

        self._update_window_rect()
        if not self._window_rect:
            raise WeChatConnectionError("Could not get window rectangle")

        logger.info(
            f"OCR listener connected. Window rect: {self._window_rect}"
        )
        self._running = True
        return True

    def _init_ocr(self) -> None:
        model_dir = self._ocr_model_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "models", "paddleocr"
        )
        model_dir = os.path.abspath(model_dir)
        os.makedirs(model_dir, exist_ok=True)

        paddle_home = os.path.join(model_dir, "home")
        os.makedirs(paddle_home, exist_ok=True)
        os.environ["PADDLE_OCR_HOME"] = paddle_home

        ocr_kwargs: Dict[str, Any] = {
            "use_angle_cls": True,
            "lang": "ch",
            "show_log": False,
            "use_gpu": True,
            "model_dir": model_dir,
        }
        if self._ocr_model_dir:
            ocr_kwargs["det_model_dir"] = os.path.join(self._ocr_model_dir, "det")
            ocr_kwargs["rec_model_dir"] = os.path.join(self._ocr_model_dir, "rec")
            ocr_kwargs["cls_model_dir"] = os.path.join(self._ocr_model_dir, "cls")

        logger.info("Loading PaddleOCR model...")
        self._ocr = PaddleOCR(**ocr_kwargs)
        logger.info("PaddleOCR model loaded")

    def _find_wechat_window(self) -> Optional[Any]:
        if not UIAUTOMATION_AVAILABLE:
            logger.warning("uiautomation not available, using full screen capture")
            return None

        titles = self.WINDOW_TITLES.get(self.platform, [])
        for title in titles:
            window = auto.WindowControl(Name=title, searchDepth=1)
            if window.Exists(1, 0):
                logger.info(f"Found {self.platform.value} window: {title}")
                return window
        return None

    def _update_window_rect(self) -> None:
        if self._wechat_window:
            try:
                rect = self._wechat_window.BoundingRectangle
                left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom

                if left == right or top == bottom:
                    logger.warning("Window appears minimized, attempting to restore...")
                    try:
                        import ctypes
                        hwnd = self._wechat_window.NativeWindowHandle
                        if hwnd:
                            SW_RESTORE = 9
                            ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
                            import time as _time
                            _time.sleep(1.0)
                            rect = self._wechat_window.BoundingRectangle
                            left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
                    except Exception as restore_err:
                        logger.debug(f"Window restore attempt failed: {restore_err}")

                if left == right or top == bottom:
                    logger.warning("Window rect is zero, window may be minimized")
                    self._window_rect = None
                    return

                self._window_rect = (left, top, right, bottom)
            except Exception as e:
                logger.error(f"Failed to get window rect: {e}")
                self._window_rect = None
        else:
            self._window_rect = None

    def _capture_message_region(self) -> Optional[Any]:
        if not self._window_rect:
            return None

        left, top, right, bottom = self._window_rect

        width = right - left
        height = bottom - top

        msg_left = int(left + width * self._crop_ratio[0])
        msg_top = int(top + height * self._crop_ratio[1])
        msg_right = int(left + width * self._crop_ratio[2])
        msg_bottom = int(top + height * self._crop_ratio[3])

        region = (msg_left, msg_top, msg_right, msg_bottom)

        try:
            screenshot = self._grab_window(bbox=region)
            return screenshot
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            return None

    def _grab_window(self, bbox: Optional[Tuple[int, int, int, int]] = None) -> Optional[Any]:
        if not WINDOWS_API_AVAILABLE or not self._wechat_window:
            if PIL_AVAILABLE and ImageGrab:
                return ImageGrab.grab(bbox=bbox) if bbox else ImageGrab.grab()
            return None

        try:
            hwnd_val = int(self._wechat_window.NativeWindowHandle)
            if not hwnd_val:
                return None

            left, top, right, bottom = self._window_rect
            width = right - left
            height = bottom - top

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            HWND = ctypes.c_void_p
            hwnd = HWND(hwnd_val)

            hwndDC = user32.GetWindowDC(hwnd)
            mfcDC = gdi32.CreateCompatibleDC(hwndDC)
            saveBitMap = gdi32.CreateCompatibleBitmap(hwndDC, width, height)
            gdi32.SelectObject(mfcDC, saveBitMap)

            user32.PrintWindow(hwnd, mfcDC, 2)

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ('biSize', ctypes.c_uint32),
                    ('biWidth', ctypes.c_long),
                    ('biHeight', ctypes.c_long),
                    ('biPlanes', ctypes.c_short),
                    ('biBitCount', ctypes.c_short),
                    ('biCompression', ctypes.c_uint32),
                    ('biSizeImage', ctypes.c_uint32),
                    ('biXPelsPerMeter', ctypes.c_long),
                    ('biYPelsPerMeter', ctypes.c_long),
                    ('biClrUsed', ctypes.c_uint32),
                    ('biClrImportant', ctypes.c_uint32),
                ]

            bmih = BITMAPINFOHEADER()
            bmih.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmih.biWidth = width
            bmih.biHeight = -height
            bmih.biPlanes = 1
            bmih.biBitCount = 32

            buf = ctypes.create_string_buffer(width * height * 4)
            gdi32.GetDIBits(mfcDC, saveBitMap, 0, height, buf, ctypes.byref(bmih), 0)

            import numpy as np
            arr = np.frombuffer(buf, dtype=np.uint8).reshape((height, width, 4))
            img = Image.fromarray(arr, 'RGBA')

            user32.ReleaseDC(hwnd, hwndDC)
            gdi32.DeleteObject(saveBitMap)
            gdi32.DeleteDC(mfcDC)

            if bbox:
                bl, bt, br, bb = bbox
                img = img.crop((bl - left, bt - top, br - left, bb - top))

            return img

        except Exception as e:
            logger.error(f"PrintWindow capture failed: {e}")
            if PIL_AVAILABLE and ImageGrab:
                return ImageGrab.grab(bbox=bbox) if bbox else ImageGrab.grab()
            return None

    def _ocr_extract(self, image: Any) -> List[Dict[str, Any]]:
        if not self._ocr or not image:
            return []

        try:
            import numpy as np
            img_array = np.array(image)
            results = self._ocr.ocr(img_array, cls=True)

            if not results or not results[0]:
                return []

            lines = []
            for item in results[0]:
                box = item[0]
                text = item[1][0]
                confidence = item[1][1]

                y_center = (box[0][1] + box[2][1]) / 2
                x_center = (box[0][0] + box[2][0]) / 2

                lines.append({
                    "text": text,
                    "confidence": confidence,
                    "y": y_center,
                    "x": x_center,
                    "box": box,
                })

            lines.sort(key=lambda l: l["y"])
            return lines

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return []

    def _group_lines_into_messages(self, lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not lines:
            return []

        messages = []
        current_group: List[Dict[str, Any]] = []
        current_y = None
        y_threshold = 15

        for line in lines:
            if current_y is not None and abs(line["y"] - current_y) > y_threshold:
                if current_group:
                    messages.append(self._parse_message_group(current_group))
                current_group = []

            current_group.append(line)
            current_y = line["y"]

        if current_group:
            messages.append(self._parse_message_group(current_group))

        return messages

    def _parse_message_group(self, group: List[Dict[str, Any]]) -> Dict[str, Any]:
        full_text = " ".join(l["text"] for l in group)
        avg_y = sum(l["y"] for l in group) / len(group)
        avg_x = sum(l["x"] for l in group) / len(group)
        min_conf = min(l["confidence"] for l in group)

        sender = ""
        content = full_text

        time_pattern = r'(\d{1,2}:\d{2}(?::\d{2})?)'
        time_match = re.search(time_pattern, full_text)
        timestamp = None
        if time_match:
            timestamp = time_match.group(1)

        separators = [r'\s*[:：]\s*', r'\s*[—\-–]\s*']
        for sep in separators:
            parts = re.split(sep, full_text, 1)
            if len(parts) >= 2 and len(parts[0]) <= 20:
                potential_sender = parts[0].strip()
                if re.match(r'^[\u4e00-\u9fff\w]+$', potential_sender):
                    sender = potential_sender
                    content = parts[1].strip()
                    break

        return {
            "full_text": full_text,
            "sender": sender,
            "content": content,
            "timestamp": timestamp,
            "y": avg_y,
            "x": avg_x,
            "confidence": min_conf,
        }

    def _detect_new_messages(
        self,
        current_lines: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        current_texts = [l["text"] for l in current_lines]
        current_hash = hashlib.md5(
            "|".join(current_texts).encode()
        ).hexdigest()

        if current_hash == self._prev_hash:
            return []

        new_texts = []
        for text in current_texts:
            if text not in self._prev_text_lines:
                new_texts.append(text)

        self._prev_text_lines = current_texts
        self._prev_hash = current_hash

        if not new_texts:
            return []

        messages = self._group_lines_into_messages(current_lines)

        new_messages = []
        for msg in messages:
            msg_key = hashlib.md5(
                f"{msg['sender']}|{msg['content']}".encode()
            ).hexdigest()

            if msg_key in self._seen_set:
                continue

            has_new_text = any(
                t in msg["full_text"] for t in new_texts
            )
            if has_new_text:
                self._seen_set.add(msg_key)
                self._seen_messages.append(msg_key)
                new_messages.append(msg)

        return new_messages

    def _poll_messages(self) -> None:
        self._update_window_rect()
        screenshot = self._capture_message_region()
        if not screenshot:
            return

        lines = self._ocr_extract(screenshot)
        if not lines:
            return

        new_messages = self._detect_new_messages(lines)

        for msg in new_messages:
            if msg["confidence"] < 0.5:
                continue

            wechat_message = WeChatMessage(
                msg_id=f"ocr_{hashlib.md5(msg['full_text'].encode()).hexdigest()[:12]}_{int(time.time())}",
                msg_type=MessageType.TEXT,
                content=msg["content"],
                conversation_id="ocr_detected",
                conversation_type=ConversationType.GROUP,
                sender_id=msg["sender"] or "unknown",
                sender_name=msg["sender"] or "unknown",
                timestamp=datetime.now(),
                raw_data=msg,
            )

            task_message = self.parser.parse_task_message(wechat_message)
            self._message_queue.put(task_message)

            self._on_message(wechat_message)
            if task_message.is_project_task:
                self._on_task_message(task_message)
                logger.info(f"Task detected: {msg['sender']}: {msg['content'][:50]}")
            else:
                logger.debug(f"Message: {msg['sender']}: {msg['content'][:50]}")

    def _run_polling_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        logger.info(f"OCR polling started (interval: {self.poll_interval}s)")

        while self._running:
            try:
                self._poll_messages()
            except Exception as e:
                logger.error(f"OCR polling error: {e}")
                self._on_error(e)

            time.sleep(self.poll_interval)

    def disconnect(self) -> None:
        self._running = False
        logger.info("OCR listener disconnected")

    async def get_next_message(self, timeout: float = 1.0) -> Optional[TaskMessage]:
        try:
            return self._message_queue.get(timeout=timeout)
        except Empty:
            return None

    async def start_listening(self) -> None:
        while self._running:
            try:
                task_message = await self.get_next_message(timeout=1.0)
                if task_message:
                    if self._callback and self._callback.on_message:
                        self._callback.on_message(task_message.original_message)
                    if task_message.is_project_task and self._callback and self._callback.on_task_message:
                        self._callback.on_task_message(task_message)
            except Exception as e:
                logger.error(f"Listening loop error: {e}")
                self._on_error(e)
                await asyncio.sleep(1)

    def start_background(self) -> None:
        if self._listener_thread and self._listener_thread.is_alive():
            logger.warning("OCR listener already running")
            return

        self._listener_thread = threading.Thread(
            target=self._run_polling_loop, daemon=True
        )
        self._listener_thread.start()
        super().start_background()
        logger.info("OCR listener started in background")

    def get_contacts(self) -> List[dict]:
        return []

    def get_rooms(self) -> List[dict]:
        return []

    def send_text(self, conversation_id: str, content: str) -> bool:
        logger.warning("OCR listener does not support sending messages")
        return False

    def calibrate(self, crop_ratio: Tuple[float, float, float, float]) -> bool:
        self._crop_ratio = crop_ratio
        logger.info(f"Calibrated crop_ratio: {crop_ratio}")

        screenshot = self._capture_message_region()
        if screenshot:
            screenshot.save("debug/calibrate_result.png")
            logger.info("Calibration screenshot saved to debug/calibrate_result.png")
            return True
        return False

    def capture_full_window(self) -> Optional[Any]:
        if not self._window_rect:
            return None
        try:
            return self._grab_window()
        except Exception as e:
            logger.error(f"Full window capture failed: {e}")
            return None

    def auto_calibrate(self) -> Tuple[float, float, float, float]:
        logger.info("Starting auto-calibration...")
        full_window = self.capture_full_window()
        if not full_window:
            logger.error("Cannot capture full window")
            return self._crop_ratio

        import numpy as np
        img_array = np.array(full_window)
        height, width = img_array.shape[:2]

        is_dark = np.mean(img_array) < 50
        if is_dark:
            logger.warning("Window appears dark, trying PrintWindow capture...")
            full_window = self._grab_window()
            if full_window:
                img_array = np.array(full_window)
                height, width = img_array.shape[:2]
                if np.mean(img_array) < 50:
                    logger.error("PrintWindow also returned dark image")
                    return self._crop_ratio

        lines = self._ocr_extract(full_window)
        if not lines:
            logger.warning("No text detected, using default message area scan...")
            crop_ratio = (0.20, 0.02, 0.98, 0.85)
            logger.info(f"Using default crop: {crop_ratio}")
            self.calibrate(crop_ratio)
            return crop_ratio

        ys = [l["y"] for l in lines]
        xs = [l["x"] for l in lines]

        min_y, max_y = min(ys), max(ys)
        min_x, max_x = min(xs), max(xs)

        crop_ratio = (
            float(min_x / width),
            float(min_y / height),
            float(max_x / width),
            float(max_y / height),
        )

        margin = 0.02
        crop_ratio = (
            max(0, crop_ratio[0] - margin),
            max(0, crop_ratio[1] - margin),
            min(1, crop_ratio[2] + margin),
            min(1, crop_ratio[3] + margin),
        )

        logger.info(f"Auto-calibration result: {crop_ratio}")
        self.calibrate(crop_ratio)
        return crop_ratio
