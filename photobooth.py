from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import cv2
from matplotlib.pyplot import draw
import mediapipe as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFont


SF_FONT = "/System/Library/Fonts/SFNS.ttf"

# RGB palette (PIL format)
BG_RGB     = (252, 252, 250)
ACCENT_RGB = (255, 188, 112)   # warm gold — frame rectangle colour
WHITE_RGB  = (255, 255, 255)
BLACK_RGB  = (20,  20,  20)
GRAY_RGB   = (65,  65,  65)
GREEN_RGB  = (120, 210,  80)

# BGR for cv2-only operations (face-detection rect)
GREEN_BGR  = (80, 210, 120)


class PhotoBoothApp:
    def __init__(self) -> None:
        self.capture = cv2.VideoCapture(0)
        if not self.capture.isOpened():
            raise RuntimeError("Could not open camera. Check camera permissions and try again.")

        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self.window_name = "Python Photobooth"
        self.output_dir  = Path("/Users/gabrielaslomiany/PyDeveloper/photobooth_pictures")
        self.output_dir.mkdir(exist_ok=True)

        self.margin = 28
        self.gap    = 24

        # 70 / 30 horizontal split
        # total_usable   = 2884
        total_usable   = 3100 #fits screen
        self.preview_w = int(0.70 * total_usable)
        self.panel_w   = total_usable - self.preview_w - self.gap
        self.preview_h = 1600
        self.panel_h   = self.preview_h
        self.canvas_w  = self.margin * 2 + total_usable
        self.canvas_h  = self.margin * 2 + self.preview_h + 86

        # Frame: 88 % of preview width, 2000:1400 aspect ratio
        self.frame_w = int(self.preview_w * 0.88)
        self.frame_h = int(self.frame_w * 1400 / 2000)
        self.frame_x = self.margin + (self.preview_w - self.frame_w) // 2
        self.frame_y = self.margin + (self.preview_h - self.frame_h) // 2

        # Strip photo dimensions (% of panel height)
        self.strip_gap     = 20
        self.strip_padding = int(self.panel_h * 0.03)
        available_h        = self.panel_h - 2 * self.strip_padding - 2 * self.strip_gap
        self.strip_photo_h = available_h // 3
        self.strip_photo_w = int(self.strip_photo_h * 2000 / 1400)
        self.strip_footer_h = 150          # always-present footer space at bottom of strip

        # Button / UI interaction rects
        self.button_rect             = (0, 0, 0, 0)
        self.date_button_rect        = (0, 0, 0, 0)
        self.black_white_button_rect = (0, 0, 0, 0)
        self.quit_button_rect        = (0, 0, 0, 0)
        self.text_box_rect           = (0, 0, 0, 0)

        self.saved_path: Path | None = None
        self.save_requested          = False
        self.date_requested          = False
        self.black_white_requested   = False
        self.quit_requested          = False
        self.text_box_focused        = False
        self.add_date_to_strip       = False
        self.black_white_strip       = False
        self.custom_text             = ""
        self.photos: list[np.ndarray] = []

        self._font_cache: dict[int, ImageFont.FreeTypeFont] = {}
        self.face_detector = None

        if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
            mp_face_detection = mp.solutions.face_detection
            self.face_detector = mp_face_detection.FaceDetection(
                model_selection=0, min_detection_confidence=0.5,
            )

        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self.on_mouse)

    # ── helpers ───────────────────────────────────────────────────────────

    def _font(self, size: int) -> ImageFont.FreeTypeFont:
        if size not in self._font_cache:
            self._font_cache[size] = ImageFont.truetype(SF_FONT, size)
        return self._font_cache[size]

    def _make_canvas(self) -> Image.Image:
        return Image.new("RGB", (self.canvas_w, self.canvas_h), BG_RGB)

    def _show(self, canvas: Image.Image) -> None:
        cv2.imshow(self.window_name, cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2BGR))

    def _draw_centered(
        self, draw: ImageDraw.Draw,
        text: str, bx: int, by: int, bw: int, bh: int,
        size: int, color: tuple,
    ) -> None:
        draw.text((bx + bw // 2, by + bh // 2), text,
                  font=self._font(size), fill=color, anchor="mm")

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
        """Wrap text into lines that fit within max_w pixels, character by character."""
        if not text:
            return []
        dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        lines: list[str] = []
        current = ""
        for char in text:
            candidate = current + char
            w = dummy.textbbox((0, 0), candidate, font=font)[2]
            if w > max_w and current:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    # ── mouse handler ─────────────────────────────────────────────────────

    def on_mouse(self, event: int, x: int, y: int, _flags: int, _param: object) -> None:
        if event != cv2.EVENT_LBUTTONDOWN or len(self.photos) != 3:
            return

        tx, ty, tw, th = self.text_box_rect
        if tx <= x <= tx + tw and ty <= y <= ty + th:
            self.text_box_focused = not self.text_box_focused
            return
        self.text_box_focused = False          # click outside box → unfocus

        bx, by, bw, bh = self.button_rect
        if bx <= x <= bx + bw and by <= y <= by + bh:
            self.save_requested = True

        dx, dy, dw, dh = self.date_button_rect
        if dx <= x <= dx + dw and dy <= y <= dy + dh:
            self.date_requested = True

        bwx, bwy, bww, bwh = self.black_white_button_rect
        if bwx <= x <= bwx + bww and bwy <= y <= bwy + bwh:
            self.black_white_requested = True

        qx, qy, qw, qh = self.quit_button_rect
        if qx <= x <= qx + qw and qy <= y <= qy + qh:
            self.quit_requested = True

    # ── main loop ─────────────────────────────────────────────────────────

    def run(self) -> None:
        try:
            for photo_number in range(1, 4):
                self.countdown(seconds=2, photo_number=photo_number)
                photo = self.take_photo()
                self.photos.append(photo)
                if photo_number < 3:
                    self.pause_between_photos(seconds=1)
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
            draw   = ImageDraw.Draw(canvas)
            draw.text(
                (self.frame_x, self.margin + 100),
                f"Photo {photo_number} in {remaining}s",
                font=self._font(54), fill=ACCENT_RGB, anchor="ls",
            )
            draw.text(
                (self.margin + 30, self.canvas_h - 36),
                "Press Q to quit",
                font=self._font(30), fill=BLACK_RGB, anchor="ls",
            )
            self._show(canvas)
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
            draw   = ImageDraw.Draw(canvas)
            draw.text(
                (self.frame_x, self.margin + 100),
                f"Change pose: {remaining}s",
                font=self._font(54), fill=ACCENT_RGB, anchor="ls",
            )
            draw.text(
                (self.margin + 30, self.canvas_h - 36),
                "Press Q to quit",
                font=self._font(30), fill=BLACK_RGB, anchor="ls",
            )
            self._show(canvas)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                raise SystemExit

    def take_photo(self) -> np.ndarray:
        ok, frame = self.capture.read()
        if not ok:
            raise RuntimeError("Could not read from camera.")
        preview = self.prepare_preview(frame)
        crop_x  = (self.preview_w - self.frame_w) // 2
        crop_y  = (self.preview_h - self.frame_h) // 2
        photo   = preview[crop_y : crop_y + self.frame_h, crop_x : crop_x + self.frame_w]
        return cv2.resize(photo, (self.strip_photo_w, self.strip_photo_h), interpolation=cv2.INTER_AREA)

    def wait_for_save(self) -> None:
        self.capture.release()
        while True:
            canvas = self.build_review_canvas()
            self._show(canvas)
            key = cv2.waitKey(1) & 0xFF

            if self.text_box_focused:
                if key in (8, 127):           # backspace / delete
                    self.custom_text = self.custom_text[:-1]
                elif key in (13, 27):         # enter / escape → unfocus
                    self.text_box_focused = False
                elif 32 <= key <= 126:        # printable ASCII
                    self.custom_text += chr(key)
                continue                     # skip global shortcuts while typing

            if key == ord("q") or self.quit_requested:
                self.quit_requested = False
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

    # ── canvas builders ───────────────────────────────────────────────────

    def build_canvas(self, frame: np.ndarray) -> Image.Image:
        preview     = self.prepare_preview(frame)
        preview     = self.draw_face_hint(preview)
        preview_pil = Image.fromarray(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB))

        canvas = self._make_canvas()
        canvas.paste(preview_pil, (self.margin, self.margin))

        draw = ImageDraw.Draw(canvas)
        draw.rectangle(
            [self.frame_x, self.frame_y,
             self.frame_x + self.frame_w, self.frame_y + self.frame_h],
            outline=ACCENT_RGB, width=5,
        )
        self.draw_strip_panel(canvas, draw)
        return canvas

    def build_review_canvas(self) -> Image.Image:
        canvas = self._make_canvas()
        strip  = self.build_strip_pil()

        left_w = int(self.canvas_w * 0.70)
        sx = max(0, (left_w - strip.width)  // 2)
        sy = max(0, (self.canvas_h - strip.height) // 2)
        canvas.paste(strip, (sx, sy))

        draw    = ImageDraw.Draw(canvas)
        right_x = left_w
        self.draw_review_buttons(draw, right_x, self.canvas_w - right_x)

        if self.saved_path:
            qx, qy, qw, qh = self.quit_button_rect
            draw.text(
                (qx + qw // 2, qy + qh + 50),
                f"Saved: {self.saved_path.name}",
                font=self._font(26), fill=GREEN_RGB,
                anchor="mt",
                stroke_width=1,
                stroke_fill=GREEN_RGB,
            )

        return canvas

    # ── panels ────────────────────────────────────────────────────────────

    def draw_strip_panel(self, canvas: Image.Image, draw: ImageDraw.Draw) -> None:
        panel_x = self.margin + self.preview_w + self.gap
        panel_y = self.margin

        draw.rectangle(
            [panel_x, panel_y, panel_x + self.panel_w, panel_y + self.panel_h],
            fill=WHITE_RGB,
        )

        for index in range(3):
            x = panel_x + (self.panel_w - self.strip_photo_w) // 2
            y = panel_y + self.strip_padding + index * (self.strip_photo_h + self.strip_gap)

            if index < len(self.photos):
                photo_pil = Image.fromarray(cv2.cvtColor(self.photos[index], cv2.COLOR_BGR2RGB))
                canvas.paste(photo_pil, (x, y))
            else:
                draw.rectangle(
                    [x, y, x + self.strip_photo_w, y + self.strip_photo_h],
                    outline=GRAY_RGB, width=2,
                )
                self._draw_centered(
                    draw, f"{index + 1}",
                    x, y, self.strip_photo_w, self.strip_photo_h,
                    80, GRAY_RGB,
                )

    def draw_review_buttons(self, draw: ImageDraw.Draw, right_x: int, right_w: int) -> None:
        bw, gap = 480, 38
        tb_pad  = 14
        tb_font = self._font(34)
        tb_inner_w = bw - 2 * tb_pad

        ascent, descent = tb_font.getmetrics()
        line_h = ascent + descent

        # Uniform height = two text lines + padding (used for both buttons and text box minimum)
        uniform_h = 2 * line_h + 2 * tb_pad + 4
        bh = uniform_h

        # Text box grows beyond uniform_h only when content exceeds two lines
        wrapped = self._wrap_text(self.custom_text, tb_font, tb_inner_w)
        n_lines = max(1, len(wrapped))
        tbh     = max(uniform_h, n_lines * line_h + 2 * tb_pad + (n_lines - 1) * 4)


        total_h = 4 * bh + tbh + 5 * gap
        start_y = max(self.margin, (self.canvas_h - total_h) // 2)
        bx      = right_x + (right_w - bw) // 2 - 400

        # ADD DATE
        y0 = start_y
        fill0 = ACCENT_RGB if self.add_date_to_strip else WHITE_RGB
        draw.rectangle([bx, y0, bx + bw, y0 + bh], fill=fill0, outline=BLACK_RGB, width=3)
        self._draw_centered(draw, "ADD DATE", bx, y0, bw, bh, 34, BLACK_RGB)
        self.date_button_rect = (bx, y0, bw, bh)

        # Text input box — height grows with content
        y1     = y0 + bh + gap
        border = ACCENT_RGB if self.text_box_focused else BLACK_RGB
        draw.rectangle([bx, y1, bx + bw, y1 + tbh], fill=WHITE_RGB, outline=border, width=3)

        if wrapped:
            for i, line in enumerate(wrapped):
                # Append blinking cursor to the last line when focused
                text_line = (line + "|") if (self.text_box_focused and i == len(wrapped) - 1) else line
                draw.text((bx + tb_pad, y1 + tb_pad + i * (line_h + 4)),
                          text_line, font=tb_font, fill=BLACK_RGB)
        elif self.text_box_focused:
            draw.text((bx + tb_pad, y1 + tb_pad), "|", font=tb_font, fill=BLACK_RGB)
        else:
            draw.text((bx + bw // 2, y1 + tbh // 2), "ADD TEXT",
                      font=tb_font, fill=GRAY_RGB, anchor="mm")
        self.text_box_rect = (bx, y1, bw, tbh)

        # B/W
        y2 = y1 + tbh + gap
        fill2 = ACCENT_RGB if self.black_white_strip else WHITE_RGB
        draw.rectangle([bx, y2, bx + bw, y2 + bh], fill=fill2, outline=BLACK_RGB, width=3)
        self._draw_centered(draw, "B/W", bx, y2, bw, bh, 34, BLACK_RGB)
        self.black_white_button_rect = (bx, y2, bw, bh)

        # SAVE
        y3 = y2 + bh + gap
        draw.rectangle([bx, y3, bx + bw, y3 + bh], fill=WHITE_RGB, outline=BLACK_RGB, width=3)
        self._draw_centered(draw, "SAVE", bx, y3, bw, bh, 34, BLACK_RGB)
        self.button_rect = (bx, y3, bw, bh)

        # Quit
        y4 = y3 + bh + gap
        draw.rectangle([bx, y4, bx + bw, y4 + bh], fill=WHITE_RGB, outline=BLACK_RGB, width=3)
        self._draw_centered(draw, "Quit", bx, y4, bw, bh, 34, BLACK_RGB)
        self.quit_button_rect = (bx, y4, bw, bh)

    # ── camera helpers ────────────────────────────────────────────────────

    def prepare_preview(self, frame: np.ndarray) -> np.ndarray:
        frame = cv2.flip(frame, 1)
        return cv2.resize(frame, (self.preview_w, self.preview_h), interpolation=cv2.INTER_AREA)

    def draw_face_hint(self, preview: np.ndarray) -> np.ndarray:
        if self.face_detector is None:
            return preview
        rgb    = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        result = self.face_detector.process(rgb)
        if not result.detections:
            return preview
        for detection in result.detections[:1]:
            box = detection.location_data.relative_bounding_box
            x   = max(0, int(box.xmin  * self.preview_w))
            y   = max(0, int(box.ymin  * self.preview_h))
            w   = min(self.preview_w - x, int(box.width  * self.preview_w))
            h   = min(self.preview_h - y, int(box.height * self.preview_h))
            cv2.rectangle(preview, (x, y), (x + w, y + h), GREEN_BGR, 2)
        return preview

    # ── strip image ───────────────────────────────────────────────────────

    def build_strip_pil(self) -> Image.Image:
        strip_w      = self.strip_photo_w + self.strip_padding * 2
        photo_sect_h = self.strip_padding * 2 + self.strip_photo_h * 3 + self.strip_gap * 2

        text_pad     = 20
        font         = self._font(30)
        text_inner_w = strip_w - 8 * text_pad
        ascent, descent = font.getmetrics()
        line_h       = ascent + descent
        line_spacing = 6

        # Collect all footer lines (date block then custom-text block)
        footer_lines: list[str] = []
        if self.add_date_to_strip:
            footer_lines += self._wrap_text(datetime.now().strftime("%d/%m/%Y"), font, text_inner_w)
        if self.custom_text:
            footer_lines += self._wrap_text(self.custom_text, font, text_inner_w)

        n        = len(footer_lines)
        footer_h = max(
            self.strip_footer_h,
            text_pad * 2 + n * line_h + max(0, n - 1) * line_spacing if n else 0,
        )
        strip_h = photo_sect_h + footer_h

        strip = Image.new("RGB", (strip_w, strip_h), WHITE_RGB)

        for index, photo in enumerate(self.photos):
            x = (strip_w - self.strip_photo_w) // 2
            y = self.strip_padding + index * (self.strip_photo_h + self.strip_gap)
            strip.paste(Image.fromarray(cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)), (x, y))

        draw   = ImageDraw.Draw(strip)
        text_y = photo_sect_h + text_pad
        for line in footer_lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw   = bbox[2] - bbox[0]
            draw.text(((strip_w - tw) // 2, text_y), line, font=font, fill=BLACK_RGB)
            text_y += line_h + line_spacing

        if self.black_white_strip:
            strip = strip.convert("L").convert("RGB")

        return strip

    def save_strip(self) -> Path:
        strip     = self.build_strip_pil()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path      = self.output_dir / f"photobooth_{timestamp}.jpg"
        strip.save(str(path), quality=95)
        return path


if __name__ == "__main__":
    try:
        PhotoBoothApp().run()
    except SystemExit:
        pass
    except Exception as exc:
        print(f"Photobooth error: {exc}")
