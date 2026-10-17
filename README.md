# Image Converter

A small desktop tool that turns DDS, TGA and BMP files into normal PNG images,
with a live preview. Plain Python and Tkinter, nothing to install.

## Run

Install Python 3.8 or newer (with Tkinter), then double-click `run.bat`,
or run `python main_gui.py`. You can also pass files or a folder:
`python main_gui.py texture.dds folder_of_images`.

## Use

1. Click **Add images** or **Add folder**.
2. Click a file to preview it. Transparent areas show over a checkerboard.
3. Press **Convert all to PNG**. Leave **Save to** empty to put each PNG next to its original.

**Save as PNG** saves just the picture you are looking at.

## Supported formats

| Format | Details |
| --- | --- |
| DDS | DXT1, DXT3, DXT5, ATI1, ATI2, DX10 variants of those, uncompressed RGB, RGBA, luminance, alpha. First mip level only |
| TGA | Indexed, true color and gray, plain or RLE, any origin |
| BMP | 1, 4, 8, 16, 24 and 32 bit |
| Others | TIFF, WebP, PSD, BC7 DDS and more when Pillow is installed (`pip install pillow`) |

## Tests

`python tests/test_image_core.py` (needs Pillow, it compares the decoders against Pillow's).

## Build an exe

Run `BUILD.bat`. The app appears in `dist\Image Converter\`.

## License

MIT, see `LICENSE`.
