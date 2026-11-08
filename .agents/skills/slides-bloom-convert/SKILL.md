---
name: slides-bloom-convert
description: Convert a PowerPoint .pptx with click-triggered animations into a PDF with Slides Bloom when the user provides a presentation and asks for an animation-aware PDF.
---

# Slides Bloom conversion

Use the bundled script to send a local `.pptx` to Slides Bloom and save the converted PDF. This is for animation-aware conversion; ordinary PDF editing or reading does not need this skill.

The default service is `https://slidesbloom.duckdns.org`. The presentation is uploaded to that service. Run the conversion only for a file the user has asked you to convert or otherwise authorized you to send there. The service accepts `.pptx` files up to 20 MiB and deletes server-side files after they are at least 24 hours old. Conversion may fail for unsupported effects or unavailable fonts; report the actual error and inspect the PDF when visual accuracy matters.

Run the bundled script with Python 3 (standard library only). Locate `scripts/convert.py` next to this `SKILL.md` and use its absolute path, so this works whether the skill is installed for one repository or for the user:

```bash
python3 /absolute/path/to/slides-bloom-convert/scripts/convert.py /absolute/path/input.pptx --output /absolute/path/output.pdf
```

Pass `--base-url http://localhost:8080` when using a local Slides Bloom instance. The script prints a JSON result containing the output path, page count, and any conversion warnings. It writes progress and errors to stderr and exits nonzero on failure. It leaves an existing output file untouched unless `--force` is supplied.

After conversion, give the user a link to the saved PDF and mention any warnings. If conversion fails, report the error; do not claim a PDF was produced. Do not retry a failed conversion automatically when the server reports an unsupported animation.
