# remove-background-ai

Remove the background from a photo with OpenAI's GPT Image 2.5 and get a transparent PNG, from the command line or from Python.

```bash
export OPENAI_API_KEY=sk-...
uvx remove-background-ai photo.jpg
```

That writes `photo-no-bg.png` next to `photo.jpg`: your original pixels, at their original size, with the background made transparent.

Sometimes, being specific about what you want to keep, and what to remove helps get better results. For example:

```bash
uvx remove-background-ai docs/images/tintin.jpg --remove "the background" --keep "the bar top on the right"
```

| Before | After |
| :---: | :---: |
| ![Tintin and Captain Haddock at a bar, on a flat tan background](https://raw.githubusercontent.com/nmpowell/remove-background-ai/main/docs/images/tintin.jpg) | ![The same panel with the background transparent and the bar top kept](https://raw.githubusercontent.com/nmpowell/remove-background-ai/main/docs/images/tintin-no-bg.png) |

> ⚠️ Much of this is AI-generated, and not formally reviewed by hand or eye. It's published chiefly for myself: for my own reference, use, and for experimentation with the whole open-source publishing process. I also *use* this code: I dogfood it. It works, for me. I also write tests, and run them to check that it works, and does what it says.

## Installation

Run it without installing, with [uv](https://docs.astral.sh/uv/):

```bash
uvx remove-background-ai photo.jpg
```

Or install it:

```bash
pip install remove-background-ai
```

It needs Python 3.14 or later and an OpenAI API key with access to the GPT Image 2.5 models. Set the key in the `OPENAI_API_KEY` environment variable; the command has no option for it. The OpenAI SDK's other variables, such as `OPENAI_BASE_URL`, `OPENAI_ORG_ID` and `OPENAI_PROJECT_ID`, work too.

Every image is a paid API call, billed by tokens. See [OpenAI's pricing](https://developers.openai.com/api/docs/pricing). The free tier cannot use GPT Image 2.5. A paid tier can, and OpenAI may ask you to verify your organisation first.

## Usage

Remove the background from one image:

```bash
remove-background-ai photo.jpg
```

Say what to keep when the photo has more than one candidate subject, and what else to remove:

```bash
remove-background-ai shelf.jpg --keep "the red backpack, including both straps" \
  --remove "the stand and its shadow on the floor"
```

Process several images into a directory, and get the results as JSON:

```bash
remove-background-ai *.jpg --output-dir cutouts --json
```

Choose where one image goes, or replace an existing output:

```bash
remove-background-ai photo.jpg -o cutout.png --force
```

Keep the model's own image instead of your original pixels (see [How it works](#how-it-works)):

```bash
remove-background-ai photo.jpg --mode generated
```

Use the faster model at a lower quality:

```bash
remove-background-ai photo.jpg --model gpt-image-2.5-flare-2026-09-08 --quality medium
```

The command prints each output path on standard output, one per line, and its progress and errors on standard error. It never overwrites a file unless you pass `--force`, and it checks for an existing output before it spends money on an API call.

## How it works

The command sends your image to the [image edit endpoint](https://developers.openai.com/api/reference/python/resources/images/methods/edit) with a prompt that says what to keep and what to remove, and asks for a PNG with a transparent background. There is no dedicated background-removal endpoint: GPT Image 2.5 redraws the image with the background removed.

The model redraws the whole image, so it can soften a label, move an edge or change a texture. By default the command keeps only the model's transparency and puts it on your original pixels. You choose between two output modes:

| Mode | What you get | Size |
| --- | --- | --- |
| `original` (default) | Your pixels, with the model's alpha channel | Your image's size |
| `generated` | The PNG the model returned, byte for byte | The size sent to the model |

In `original` mode the transparency is still the model's work. An edge can land a few pixels off, and a thin band of the old background can survive along the subject's outline: in testing, a strip of brick wall stayed along the top of a backpack. `generated` mode gives cleaner edges, because the model redraws them. Look at the result on a dark and a light backdrop before you rely on it. `generated` mode keeps the provenance metadata (C2PA) that OpenAI embeds in the PNG. `original` mode writes a new file, so that metadata is lost.

### Image sizes

GPT Image 2.5 only produces images whose width and height are multiples of 16, with an aspect ratio no wider than 3:1 and an area of 655,360 to 8,294,400 pixels. Anything over 3,686,400 pixels (2560×1440) is experimental. The command sends your image at the nearest size the model can produce, never an experimental one, and scales the returned transparency back to your image's size.

| Your image | Sent to the model | Why |
| --- | --- | --- |
| 1024×1024 | 1024×1024 | Already a size the model produces |
| 1920×1080 | 1920×1088 | 1080 is not a multiple of 16 |
| 512×512 | 816×816 | Below the minimum area |
| 6000×4000 | 2336×1552 | Above the largest standard area |
| 3000×900 | refused | Wider than 3:1 |

Sending 1920×1080 as 1920×1088 changes the aspect ratio slightly. Scaling the transparency back to 1920×1080 undoes that change, so the cutout does not shift.

The command first turns the image upright using its EXIF orientation. It accepts any format Pillow can open (JPEG, PNG, WebP, TIFF and others) in any colour mode, and always writes an 8-bit RGBA PNG. If your image already has transparency, the output never makes it more opaque. An embedded RGB colour profile goes to the model with the image and stays in the `original` output. Other profiles would describe the wrong colours after conversion, so they are dropped. CMYK images are converted to RGB without colour management, so their colours can shift; convert them to RGB yourself first if colour matters. EXIF data is not copied. Animated images are refused.

### Masks

If the model keeps the wrong thing, give it a mask: an image the same size as the photo (after EXIF rotation), white where the subject is and black elsewhere.

```bash
remove-background-ai photo.jpg --mask subject.png
```

Grey at half intensity or brighter counts as white. The mask guides the model, which can still stray over its edges.

## JSON output

`--json` replaces the list of paths with one JSON array. Each image gets an object, in the order given, whether it succeeded or failed:

```json
[
  {
    "input": "mug.jpg",
    "output": "mug-no-bg.png",
    "mode": "original",
    "model": "gpt-image-2.5-sunburst-2026-09-08",
    "quality": "medium",
    "source_size": "1300x1132",
    "model_size": "1312x1136",
    "output_size": "1300x1132",
    "request_id": "req_e4351b4660894c96ad6f08a86fc013aa",
    "usage": {
      "input_tokens": 1618,
      "output_tokens": 440,
      "total_tokens": 2058,
      "input_tokens_details": {"image_tokens": 1476, "text_tokens": 142},
      "output_tokens_details": {"image_tokens": 440, "text_tokens": 0}
    }
  },
  {
    "input": "broken.png",
    "error": "broken.png cannot be read as an image: cannot identify image file 'broken.png'"
  }
]
```

`usage` is whatever token counts the API reported, or `null`. Errors also go to standard error, so keep the two streams apart when you parse the JSON.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Every image succeeded |
| 1 | Interrupted (Ctrl-C), or a broken pipe |
| 2 | The command line was wrong: an unknown option, a missing file, `-o` or `--mask` with several images, `-o` with `--output-dir`, an output that is also an input or the mask, or two images that would write the same output |
| 3 | The tool refused an image or an output before or after the API call: it cannot be read, is animated, is wider than 3:1, its mask does not match, or the output exists or cannot be written |
| 4 | The OpenAI call failed or returned an unusable image, or `OPENAI_API_KEY` is not set |

With several images the command carries on after a failure. If any image failed, it exits with 4 when at least one failure was an API failure, and 3 otherwise.

## Timeouts and retries

The OpenAI client waits up to 300 seconds on each network operation and retries twice after a rate limit, a server error, a dropped connection or a timeout, pausing between attempts as the server asks. There is no overall deadline, so a slow image can take many minutes. A retried request can be billed more than once, because the server may have finished the first attempt.

## Python library

```python
from pathlib import Path

from remove_background_ai import RemovalOptions, remove_background

cutout = remove_background(
    Path("photo.jpg"),
    options=RemovalOptions(keep="the red backpack", quality="medium"),
)
Path("photo-no-bg.png").write_bytes(cutout.png)
print(cutout.model_size, cutout.request_id)
```

`remove_background` validates its arguments with Pydantic and raises `pydantic.ValidationError` for the wrong types. It takes a `Path` (not a `str`) as its only positional argument; `options`, `mask` and `editor` are keyword-only. `RemovalOptions` takes `model` (default `gpt-image-2.5-sunburst-2026-09-08`), `quality` (`low`, `medium`, `high`, `xhigh`, `max` or `auto`; default `high`), `mode` (`original` or `generated`), `keep` and `remove`.

It returns a `Cutout` holding the PNG bytes and their metadata; `cutout.model_dump(mode="json")` gives the metadata shown under [JSON output](#json-output), without the image. It raises `InvalidInputError` when it refuses an image and `EditError` when the API call fails; both are `RemoveBackgroundError`s.

To change the timeout or retries, pass your own client:

```python
from pathlib import Path

from openai import OpenAI

from remove_background_ai import OpenAIImageEditor, remove_background

editor = OpenAIImageEditor(OpenAI(timeout=600, max_retries=0))
cutout = remove_background(Path("photo.jpg"), editor=editor)
```

Any object with an `edit(EditRequest) -> EditResponse` method can stand in for `OpenAIImageEditor`, which is how the tests run without the API.

## CLI reference

<!-- [[[cog
import cog
from click.testing import CliRunner
from remove_background_ai.cli import cli

result = CliRunner().invoke(cli, ["--help"], terminal_width=88)
assert result.exit_code == 0, result.output
cog.out("```\n" + result.stdout.replace("Usage: cli", "Usage: remove-background-ai") + "```\n")
]]] -->
```
Usage: remove-background-ai [OPTIONS] IMAGES...

  Send each image to GPT Image 2.5 and write a transparent PNG. By default, the result
  keeps the original pixels and size and takes only transparency from the model. Set
  OPENAI_API_KEY before running this command.

  Examples:

      remove-background-ai photo.jpg
      remove-background-ai photo.jpg -o portrait.png
      remove-background-ai photo.jpg other.png -d cutouts --json
      remove-background-ai photo.jpg --keep "the red backpack, including both straps"

Options:
  -o, --output FILE               Write the PNG to FILE.
  -d, --output-dir DIRECTORY      Write PNGs to DIRECTORY.
  --force                         Replace output files that already exist.
  --keep TEXT                     What to keep, for example the red backpack and its
                                  straps.
  --remove TEXT                   What to remove besides the background.
  --mask FILE                     Mask FILE: white keeps, black removes; same size as
                                  the image.
  --mode [original|generated]     Keep original pixels and size, or use the generated
                                  image.  [default: original]
  --model [gpt-image-2.5-sunburst-2026-09-08|gpt-image-2.5-sunburst|gpt-image-2.5-flare-2026-09-08|gpt-image-2.5-flare]
                                  GPT Image model to use.  [default: gpt-
                                  image-2.5-sunburst-2026-09-08]
  --quality [low|medium|high|xhigh|max|auto]
                                  Image edit quality.  [default: high]
  --json                          Write a JSON array to stdout.
  --version                       Show the version and exit.
  --help                          Show this message and exit.

  Exit codes: 0 success; 1 general failure; 2 usage error; 3 input or output refused; 4
  image edit failed.
```
<!-- [[[end]]] -->

## Development

```bash
git clone https://github.com/nmpowell/remove-background-ai
cd remove-background-ai
uv sync --locked
uv run pytest
uv run mypy
uv run ruff check .
uv run ruff format --check .
```

The tests run without the API, except one live test that makes a real call and costs one image. It is skipped unless you ask for it:

```bash
RUN_LIVE_OPENAI_TESTS=1 OPENAI_API_KEY=sk-... uv run pytest -m live
```

After changing the command's options, regenerate the CLI reference above with `uv run cog -r README.md`. The test suite fails while the reference is out of date.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
