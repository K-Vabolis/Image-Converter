# Image-Converter
Tiny Windows desktop tool that converts DDS, TGA and BMP textures to PNG, with live preview and batch conversion. Pure Python and Tkinter.
# Image Converter

A small desktop tool that converts **DDS, TGA and BMP** textures to **PNG**, with a live preview and batch conversion.

Pure Python and Tkinter. The built-in decoders need no dependencies, and Pillow is optional.

## Features

- Batch convert files or whole folders
- Live preview with a checkerboard behind transparent areas
- Save next to the originals or into a folder of your choice
- Command-line arguments, so you can drag files onto it or launch it from scripts
- Optional standalone `.exe` build

## Quick start

1. Install [Python 3.8+](https://www.python.org/downloads/) with Tkinter (tick "tcl/tk" and "Add Python to PATH").
2. Double-click `run.bat`, or run:

```
python main_gui.py
python main_gui.py texture.dds folder_of_images
```

## Usage

1. Click **Add images** or **Add folder**.
2. Click a file to preview it.
3. Press **Convert all to PNG**. Leave **Save to** empty to put each PNG next to its original.

**Save as PNG** saves only the image you're currently previewing.

## Supported formats

| Format | Details |
| --- | --- |
| DDS | DXT1, DXT3, DXT5, ATI1, ATI2, DX10 variants of those, uncompressed RGB, RGBA, luminance, alpha. First mip level only |
| TGA | Indexed, true color and gray, plain or RLE, any origin |
| BMP | 1, 4, 8, 16, 24 and 32 bit |
| Others | TIFF, WebP, PSD, BC7 DDS and more if Pillow is installed (`pip install pillow`) |

## Tests

```
python tests/test_image_core.py
```

Requires Pillow. The tests compare the built-in decoders against Pillow's output.

## Build an exe

Run `BUILD.bat` (uses PyInstaller). The app appears in `dist\Image Converter\`. Share the whole folder, not just the exe.

## License

MIT. See [LICENSE](LICENSE).
