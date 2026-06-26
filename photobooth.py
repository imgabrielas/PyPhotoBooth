from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np


HOT_PINK = (180, 105, 255)  # BGR for OpenCV
WHITE = (255, 255, 255)
BLACK = (20, 20, 20)
GRAY = (65, 65, 65)
GREEN = (80, 210, 120)


class PhotoBoothApp:
    def __init__(self) -> None:
        self.capture = cv2.VideoCapture(0)
        if not self.capture.isOpened():
            raise RuntimeError("Could not open camera. Check camera permissions and try again.")

        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self.window_name = "Python Photobooth"
        self.output_dir = Path("/Users/gabrielaslomiany/PyDeveloper/photobooth_pictures")
        self.output_dir.mkdir(exist_ok=True)

        self.preview_w = 2560
        self.preview_h = 1600
        self.panel_w = 300
        self.panel_h = self.preview_h
        self.gap = 24
        self.margin = 28
        self.canvas_w = self.margin * 2 + self.preview_w + self.gap + self.panel_w
        self.canvas_h = self.margin * 2 + self.preview_h + 86

        self.frame_w = 2000
        self.frame_h = 1400
        self.frame_x = self.margin + (self.preview_w - self.frame_w) // 2
        self.frame_y = self.margin + (self.preview_h - self.frame_h) // 2

        self.strip_photo_w = 240
        self.strip_photo_h = 160
        self.strip_padding = 18
        self.strip_gap = 20

        self.button_rect = (0, 0, 0, 0)
        self.date_button_rect = (0, 0, 0, 0)
        self.black_white_button_rect = (0, 0, 0, 0)
        self.saved_path: Path | None = None
        self.save_requested = False
        self.date_requested = False
        self.black_white_requested = False
        self.add_date_to_strip = False
        self.black_white_strip = False
        self.photos: list[np.ndarray] = []
        self.face_detector = None

        # MediaPipe is initialized so the project uses both requested libraries.
        # Face detection is optional feedback and does not block taking photos.
        if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
            mp_face_detection = mp.solutions.face_detection
            self.face_detector = mp_face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=0.5,
            )

        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self.on_mouse)

    def on_mouse(self, event: int, x: int, y: int, _flags: int, _param: object) -> None:
        if event != cv2.EVENT_LBUTTONDOWN or len(self.photos) != 3:
            return

        bx, by, bw, bh = self.button_rect
        if bx <= x <= bx + bw and by <= y <= by + bh:
            self.save_requested = True

        dx, dy, dw, dh = self.date_button_rect
        if dx <= x <= dx + dw and dy <= y <= dy + dh:
            self.date_requested = True

        bwx, bwy, bww, bwh = self.black_white_button_rect
        if bwx <= x <= bwx + bww and bwy <= y <= bwy + bwh:
            self.black_white_requested = True

    def run(self) -> None:
        try:
            for photo_number in range(1, 4):
                self.countdown(seconds=10, photo_number=photo_number)
                photo = self.take_photo()
                self.photos.append(photo)

                if photo_number < 3:
                    self.pause_between_photos(seconds=5)

            self.wait_for_save()
        finally:
            if self.face_detector is not None:
                self.face_detector.close()
            self.capture.release()
            cv2.destroyAllWindows()

    def countdown(self, seconds: int, photo_number: int) -> None:
        start = time.monotonic()

        while True:
            remaining = seconds - int(time.monotonic() - start)
            if remaining <= 0:
                break

            ok, frame = self.capture.read()
            if not ok:
                continue

            canvas = self.build_canvas(frame)
            self.draw_text(
                canvas,
                f"Photo {photo_number} in {remaining}s",
                (self.margin + 28, self.margin + 58),
                1.25,
                HOT_PINK,
                3,
            )
            self.draw_text(
                canvas,
                "Press Q to quit",
                (self.margin + 30, self.canvas_h - 36),
                0.7,
                WHITE,
                2,
            )
            cv2.imshow(self.window_name, canvas)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                raise SystemExit

    def pause_between_photos(self, seconds: int) -> None:
        start = time.monotonic()

        while True:
            remaining = seconds - int(time.monotonic() - start)
            if remaining <= 0:
                break

            ok, frame = self.capture.read()
            if not ok:
                continue

            canvas = self.build_canvas(frame)
            self.draw_text(
                canvas,
                f"Change pose: {remaining}",
                (self.margin + 28, self.margin + 58),
                1.15,
                HOT_PINK,
                3,
            )
            cv2.imshow(self.window_name, canvas)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                raise SystemExit

    def take_photo(self) -> np.ndarray:
        ok, frame = self.capture.read()
        if not ok:
            raise RuntimeError("Could not read from camera.")

        preview = self.prepare_preview(frame)
        crop_x = (self.preview_w - self.frame_w) // 2
        crop_y = (self.preview_h - self.frame_h) // 2
        photo = preview[crop_y : crop_y + self.frame_h, crop_x : crop_x + self.frame_w]
        return cv2.resize(photo, (self.strip_photo_w, self.strip_photo_h), interpolation=cv2.INTER_AREA)

    def wait_for_save(self) -> None:
        while True:
            ok, frame = self.capture.read()
            if not ok:
                canvas = np.zeros((self.canvas_h, self.canvas_w, 3), dtype=np.uint8)
            else:
                canvas = self.build_canvas(frame)

            self.draw_save_button(canvas)

            if self.saved_path:
                self.draw_text(
                    canvas,
                    f"Saved: {self.saved_path.name}",
                    (self.margin + 28, self.canvas_h - 36),
                    0.65,
                    GREEN,
                    2,
                )
            else:
                self.draw_text(
                    canvas,
                    "Click SAVE, ADD DATE, or B/W",
                    (self.margin + 28, self.canvas_h - 36),
                    0.7,
                    WHITE,
                    2,
                )

            cv2.imshow(self.window_name, canvas)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key == ord("d") or self.date_requested:
                self.date_requested = False
                self.add_date_to_strip = not self.add_date_to_strip
                self.saved_path = None

            if key == ord("b") or self.black_white_requested:
                self.black_white_requested = False
                self.black_white_strip = not self.black_white_strip
                self.saved_path = None

            if key == ord("s") or self.save_requested:
                self.save_requested = False
                self.saved_path = self.save_strip()

    def build_canvas(self, frame: np.ndarray) -> np.ndarray:
        canvas = np.full((self.canvas_h, self.canvas_w, 3), BLACK, dtype=np.uint8)
        preview = self.prepare_preview(frame)
        preview = self.draw_face_hint(preview)

        preview_x = self.margin
        preview_y = self.margin
        canvas[preview_y : preview_y + self.preview_h, preview_x : preview_x + self.preview_w] = preview

        cv2.rectangle(
            canvas,
            (self.frame_x, self.frame_y),
            (self.frame_x + self.frame_w, self.frame_y + self.frame_h),
            HOT_PINK,
            5,
        )

        self.draw_strip_panel(canvas)
        return canvas

    def prepare_preview(self, frame: np.ndarray) -> np.ndarray:
        frame = cv2.flip(frame, 1)
        return cv2.resize(frame, (self.preview_w, self.preview_h), interpolation=cv2.INTER_AREA)

    def draw_face_hint(self, preview: np.ndarray) -> np.ndarray:
        if self.face_detector is None:
            return preview

        rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        result = self.face_detector.process(rgb)

        if not result.detections:
            return preview

        for detection in result.detections[:1]:
            box = detection.location_data.relative_bounding_box
            x = max(0, int(box.xmin * self.preview_w))
            y = max(0, int(box.ymin * self.preview_h))
            w = min(self.preview_w - x, int(box.width * self.preview_w))
            h = min(self.preview_h - y, int(box.height * self.preview_h))
            cv2.rectangle(preview, (x, y), (x + w, y + h), GREEN, 2)

        return preview

    def draw_strip_panel(self, canvas: np.ndarray) -> None:
        panel_x = self.margin + self.preview_w + self.gap
        panel_y = self.margin
        cv2.rectangle(
            canvas,
            (panel_x, panel_y),
            (panel_x + self.panel_w, panel_y + self.panel_h),
            WHITE,
            -1,
        )
        cv2.rectangle(
            canvas,
            (panel_x, panel_y),
            (panel_x + self.panel_w, panel_y + self.panel_h),
            HOT_PINK,
            5,
        )

        if len(self.photos) == 3:
            strip_preview = self.build_strip_image()
            x = panel_x + (self.panel_w - strip_preview.shape[1]) // 2
            y = panel_y + self.strip_padding
            canvas[y : y + strip_preview.shape[0], x : x + strip_preview.shape[1]] = strip_preview
            return

        for index in range(3):
            x = panel_x + (self.panel_w - self.strip_photo_w) // 2
            y = panel_y + self.strip_padding + index * (self.strip_photo_h + self.strip_gap)

            if index < len(self.photos):
                canvas[y : y + self.strip_photo_h, x : x + self.strip_photo_w] = self.photos[index]
                cv2.rectangle(canvas, (x, y), (x + self.strip_photo_w, y + self.strip_photo_h), HOT_PINK, 3)
            else:
                cv2.rectangle(canvas, (x, y), (x + self.strip_photo_w, y + self.strip_photo_h), GRAY, 2)
                self.draw_text(canvas, f"{index + 1}", (x + 105, y + 94), 1.2, GRAY, 3)

    def draw_save_button(self, canvas: np.ndarray) -> None:
        bw = 94
        bh = 48
        gap = 6
        total_w = bw * 3 + gap * 2
        bx = self.margin + self.preview_w + self.gap + (self.panel_w - total_w) // 2
        by = self.margin + self.panel_h + 22
        self.button_rect = (bx, by, bw, bh)
        self.date_button_rect = (bx + bw + gap, by, bw, bh)
        self.black_white_button_rect = (bx + (bw + gap) * 2, by, bw, bh)

        cv2.rectangle(canvas, (bx, by), (bx + bw, by + bh), HOT_PINK, -1)
        cv2.rectangle(canvas, (bx, by), (bx + bw, by + bh), WHITE, 2)
        self.draw_text(canvas, "SAVE", (bx + 12, by + 31), 0.62, WHITE, 2)

        dx, dy, dw, dh = self.date_button_rect
        date_color = GREEN if self.add_date_to_strip else HOT_PINK
        cv2.rectangle(canvas, (dx, dy), (dx + dw, dy + dh), date_color, -1)
        cv2.rectangle(canvas, (dx, dy), (dx + dw, dy + dh), WHITE, 2)
        self.draw_text(canvas, "ADD DATE", (dx + 5, dy + 30), 0.43, WHITE, 2)

        bwx, bwy, bww, bwh = self.black_white_button_rect
        black_white_color = GREEN if self.black_white_strip else HOT_PINK
        cv2.rectangle(canvas, (bwx, bwy), (bwx + bww, bwy + bwh), black_white_color, -1)
        cv2.rectangle(canvas, (bwx, bwy), (bwx + bww, bwy + bwh), WHITE, 2)
        self.draw_text(canvas, "B/W", (bwx + 16, bwy + 31), 0.62, WHITE, 2)

    def save_strip(self) -> Path:
        strip = self.build_strip_image()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / f"photobooth_{timestamp}.jpg"
        cv2.imwrite(str(path), strip)
        return path

    def build_strip_image(self) -> np.ndarray:
        strip_w = self.strip_photo_w + self.strip_padding * 2
        strip_h = self.strip_padding * 2 + self.strip_photo_h * 3 + self.strip_gap * 2
        strip = np.full((strip_h, strip_w, 3), WHITE, dtype=np.uint8)

        for index, photo in enumerate(self.photos):
            x = self.strip_padding
            y = self.strip_padding + index * (self.strip_photo_h + self.strip_gap)
            strip[y : y + self.strip_photo_h, x : x + self.strip_photo_w] = photo
            cv2.rectangle(strip, (x, y), (x + self.strip_photo_w, y + self.strip_photo_h), HOT_PINK, 3)

        if self.add_date_to_strip:
            strip = self.add_date_footer(strip)

        if self.black_white_strip:
            strip = self.convert_to_black_white(strip)

        return strip

    @staticmethod
    def convert_to_black_white(strip: np.ndarray) -> np.ndarray:
        grayscale = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(grayscale, cv2.COLOR_GRAY2BGR)

    def add_date_footer(self, strip: np.ndarray) -> np.ndarray:
        footer_h = 54
        strip_h, strip_w = strip.shape[:2]
        dated_strip = np.full((strip_h + footer_h, strip_w, 3), WHITE, dtype=np.uint8)
        dated_strip[:strip_h, :strip_w] = strip

        date_text = datetime.now().strftime("%d/%m/%Y")
        scale = 0.72
        thickness = 2
        (text_w, _text_h), _baseline = cv2.getTextSize(date_text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
        x = (strip_w - text_w) // 2
        y = strip_h + 35
        self.draw_text(dated_strip, date_text, (x, y), scale, BLACK, thickness)
        return dated_strip

    @staticmethod
    def draw_text(
        image: np.ndarray,
        text: str,
        origin: tuple[int, int],
        scale: float,
        color: tuple[int, int, int],
        thickness: int,
    ) -> None:
        cv2.putText(
            image,
            text,
            origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color,
            thickness,
            cv2.LINE_AA,
        )


if __name__ == "__main__":
    try:
        PhotoBoothApp().run()
    except SystemExit:
        pass
    except Exception as exc:
        print(f"Photobooth error: {exc}")

        
# changes made to the code:
#  added "s" to the countdown text to indicate seconds remaining
#  widened the gap between the photos in the strip panel from 12 to 20 pixels
#  added date the the saved photo
