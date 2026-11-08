# PyPhotobooth

A retro photo booth that runs in your browser. Take three photos, add a date or a short caption, switch to black and white for a vintage look, and download your photo strip.

**Live demo:** https://imgabrielas.github.io/PyPhotoBooth/

## How it works

1. **Start:** click START or press `Space`.
2. **Capture:** position yourself in the orange frame. The booth counts down and takes 3 photos, shown on the right as previews.
3. **Picture pick-up:** your strip comes out of the printer. Toggle the date, add a caption (max 20 characters), switch B/W on or off, then click **SAVE** to download it as a PNG.

Press `Q` or `Esc` at any time to go back to the start.

## From desktop app to web app

PyPhotobooth started as a desktop Python app built with Tkinter, OpenCV and MediaPipe. I rebuilt it as a web app so anyone can use it from a link, without installing Python.

What changed:

- **Interface:** Tkinter windows became plain HTML, CSS and JavaScript. The original hand-drawn illustrations are reused as the screens, with real buttons and the camera view layered on top.
- **Camera:** OpenCV capture was replaced by the browser's `getUserMedia` API.
- **Photo strip:** compositing, the B/W filter, date and caption are done with `<canvas>` in the browser, and SAVE downloads the strip directly.
- **Hosting:** everything runs client side, so the app is served for free with GitHub Pages. Photos never leave your device.

## Original Python version

The original desktop code has been moved to [`app demo/`](app%20demo/). It is kept as a reference for how the project started and can still be run locally with Python.

## Project structure

```
PyPhotobooth/
├── index.html      # the three screens
├── style.css       # layout and styling
├── app.js          # camera, countdown, strip, save
├── assets/         # hand-drawn screen illustrations
└── app demo/       # original Python desktop app
```

## Run locally

The camera only works over `https` or on `localhost`, so serve the folder rather than opening the file directly:

```bash
python -m http.server 8000
```

Then open http://localhost:8000.

## Author

Made by [imgabrielas](https://github.com/imgabrielas), 2026.